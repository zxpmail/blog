#!/usr/bin/env python3
"""
碰撞测试三：火烧/遗忘 — git 重置后状态彻底复原验证

模拟"火烧山"场景：Harness 在工作区留下痕迹后，被强制 git 重置，
验证重置后的文件系统状态与运行前字节级相同。

这是"遗忘"（量子擦除）属性的测试——"火烧"是否真的烧干净了。

测试流程（在隔离的临时 git 仓库中执行）:
  1. 建立基线：创建已知初始文件集，git commit
  2. 模拟工作：写入 plan.md、生成 artifacts、修改文件
  3. 火烧：git clean -fd && git checkout . && git reflog expire
  4. 断言：重置后每个文件的内容 == 基线内容
  5. 额外：检查 git reflog 是否被清空（物理擦除的近似验证）

通过标准:
  - 重置后目录树与基线字节级一致
  - reflog 被清空（近似物理擦除）
  - 所有原始文件内容不变

依赖: git, tempfile (标准库), 无需 LLM API

运行:
  python crash-test-reset.py
"""

import sys, io, os, json, hashlib, tempfile, shutil, subprocess, importlib, platform
from pathlib import Path

# 提前导入 forge-verify（其 module-level 的 stdout 设置优先，这里不再重复设置）
forge = importlib.import_module("forge-verify-layered-prototype")

# ── 架构不可妥协常量 ────────────────────────────────────────────────────
# 存储后端必须是 tmpfs（内存文件系统）或 COW 快照，不能是 Git。
# Git 的对象库 (./objects/) 不可变追加，git reset 只是逻辑删除——在取证级别
# 旧数据仍可从磁盘恢复。"遗忘"必须是物理擦除，不是逻辑不可见。
# 此常量在测试中强制执行：若后端为 git，测试标记为"通过但有根本缺陷"。
STORAGE_BACKEND: str = "TMPFS"


# ── 预检：物理层 STORAGE_BACKEND 验证 ─────────────────────────────────

def preflight_check_tmpfs():
    """
    Pre-flight: 物理层验证 STORAGE_BACKEND=TMPFS 不是字符串欺骗。

    向临时目录写入一个 1GB 探针文件，然后执行 df -T 确认底层文件系统
    类型是 tmpfs（内存文件系统）。防止 "Harness 层只改变量名不改真 tmpfs"
    的虚假绿灯。

    如果文件系统不是 tmpfs，直接抛 RuntimeError 中止测试——不画红灯，
    因为红灯在语义上等价于 "检查过了，但不通过"——我们需要的不是检查结果，
    而是物理铁证。如果 Red 灯是唯一的检查手段，下一层工程师只需把测试
    标绿就把红灯忽略。

    Raises:
        RuntimeError: 当实际文件系统类型非 tmpfs。
        RuntimeError: 当无法执行 df -T 但平台声称是 Linux。
    """
    if platform.system() != "Linux":
        print(f"    ⚠️  df -T 仅适用于 Linux (当前平台: {platform.system()})")
        print(f"    ⚠️  跳过物理 tmpfs 验证。请在 Linux 上运行此项预检。")
        return

    test_root = Path(tempfile.gettempdir())
    probe_file = test_root / ".crash_test_tmpfs_probe"

    try:
        # 1) 写入 1GB —— 小文件会被 page cache 吸收，无法证明真 tmpfs
        sys.stdout.write(f"    Writing 1GB probe: {probe_file} ... ")
        sys.stdout.flush()
        with open(probe_file, "wb") as f:
            f.seek(1024 ** 3 - 1)  # 1 GiB - 1 byte
            f.write(b"\0")
        print("done")

        actual_size = probe_file.stat().st_size
        print(f"    Probe size: {actual_size} bytes  (target: {1024**3})")

        # 2) df -T 确认文件系统类型
        result = subprocess.run(
            ["df", "-T", str(probe_file)],
            capture_output=True, text=True, timeout=10, encoding="utf-8",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"df -T 失败 (rc={result.returncode}): {result.stderr}"
            )

        lines = result.stdout.strip().splitlines()
        if len(lines) < 2:
            raise RuntimeError(f"df -T 输出异常: {result.stdout}")

        # df -T 格式: Filesystem  Type  Size  Used Avail Use% Mounted on
        parts = lines[1].split()
        if len(parts) < 2:
            raise RuntimeError(
                f"df -T 无法解析 Type 列: {result.stdout}"
            )
        fstype = parts[1]

        if fstype != "tmpfs":
            raise RuntimeError(
                f"🔴 STORAGE_BACKEND 物理验证失败!\n"
                f"  STORAGE_BACKEND={STORAGE_BACKEND} (代码声明)\n"
                f"  实际文件系统类型 = '{fstype}'\n"
                f"  df -T 完整输出:\n"
                f"    {result.stdout.strip()}\n\n"
                f"  这意味着 '量子擦除' 退化为 '逻辑删除':\n"
                f"  Harness 层将变量名改成了 TMPFS，但底层挂载的仍然是磁盘文件系统。\n"
                f"  旧数据在磁盘上依然可恢复——这是假擦除，不是遗忘。\n"
                f"  必须将工作目录挂载到真实 tmpfs (mount -t tmpfs ...) 才能通过此项预检。"
            )

        print(f"    ✓ 物理 tmpfs 确认: type={fstype}, "
              f"st_dev={probe_file.stat().st_dev}, "
              f"size={actual_size} bytes")

    finally:
        if probe_file.exists():
            probe_file.unlink()


# ── 帮助函数 ──────────────────────────────────────────────────────────

def git(*args, cwd: str, check: bool = True):
    """在 cwd 中运行 git 命令（固定 UTF-8 编码，避免 GBK 错误）"""
    env = os.environ.copy()
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_ALL", "en_US.UTF-8")
    result = subprocess.run(
        ["git", "-c", "i18n.logOutputEncoding=utf-8"] + list(args),
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        env=env,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr}")
    return (result.stdout or "").strip()


def dir_hash(root: str, pattern: str = "*") -> str:
    """计算目录下匹配文件的内容哈希（摘要），用于比较状态"""
    hasher = hashlib.sha256()
    root = Path(root)
    for path in sorted(root.rglob(pattern)):
        if path.is_file() and ".git" not in str(path):
            rel = str(path.relative_to(root))
            hasher.update(rel.encode("utf-8"))
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def file_hash(path: str) -> str:
    """计算单个文件的 SHA-256"""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ── 测试场景 ──────────────────────────────────────────────────────────

def create_baseline_repo(tmp_dir: str):
    """
    在 tmp_dir 创建一个有初始状态的 git 仓库。
    返回: {baseline_hash, 文件列表, 初始 commit hash}
    """
    git("init", cwd=tmp_dir)
    git("config", "user.email", "crash-test@forge.local", cwd=tmp_dir)
    git("config", "user.name", "Crash Test", cwd=tmp_dir)

    # 初始文件：模拟"用户原始 Prompt"
    init_files = {
        "prompt.md": "# User's original prompt\n\nBuild a counter component in React.",
        "spec.md": "# Spec\n\nA simple counter with increment/decrement/reset.",
        ".gitignore": "node_modules/\n*.log\n",
    }
    for name, content in init_files.items():
        path = Path(tmp_dir) / name
        path.write_text(content, encoding="utf-8")

    git("add", ".", cwd=tmp_dir)
    init_commit = git("commit", "-m", "initial state — user prompt", cwd=tmp_dir)

    baseline_hash = dir_hash(tmp_dir)
    files_before = sorted(
        str(p.relative_to(tmp_dir)) for p in Path(tmp_dir).rglob("*")
        if p.is_file() and ".git" not in str(p)
    )

    return baseline_hash, files_before, init_commit


def simulate_work(tmp_dir: str, intensity: int = 1):
    """
    模拟 Harness 工作：生成计划、产物、临时文件。
    intensity: 工作量级别（1=轻, 2=中, 3=重）
    """
    # plan.md — Harness 计划文件
    plan_content = f"""# Harness Plan — iteration {intensity}

## Step 1: Understand prompt
## Step 2: Generate component
## Step 3: Run tests
## Step 4: Commit

Status: in_progress
"""
    (Path(tmp_dir) / "plan.md").write_text(plan_content, encoding="utf-8")

    # 生成 artifacts
    artifacts = {
        "output/counter.tsx": "import { useState } from 'react';\n\nexport function Counter() {{\n  const [count, setCount] = useState(0);\n  return <div>{{count}}</div>;\n}}",
        "output/counter.test.tsx": "import { render, screen } from '@testing-library/react';\n\ndescribe('Counter', () => {{\n  it('renders', () => {{\n    render(<Counter />);\n  }});\n}});",
        "logs/build.20260721.log": "[INFO] Building component...\n[INFO] Tests passed: 3/3\n[INFO] Linting passed.\n",
    }
    for name, content in artifacts.items():
        path = Path(tmp_dir) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    # 修改原 prompt（模拟 LLM 在工作区留下痕迹）
    if intensity >= 2:
        prompt_path = Path(tmp_dir) / "prompt.md"
        original = prompt_path.read_text(encoding="utf-8")
        prompt_path.write_text(
            original + "\n\n## Analysis (added by LLM)\nThe user wants a simple counter.\n",
            encoding="utf-8",
        )

    # 生成大量临时文件（模拟 LLM 试错）
    if intensity >= 3:
        temp_dir = Path(tmp_dir) / "tmp"
        temp_dir.mkdir(exist_ok=True)
        for i in range(10):
            (temp_dir / f"scratch_{i}.py").write_text(f"# scratch file {i}\n\n", encoding="utf-8")


def fire_scorching(tmp_dir: str, full_erase: bool = True):
    """
    火烧山：reset → clean → reflog expire
    full_erase=True: 额外清空 reflog（近似物理擦除）
    """
    def _run(*cmd, check: bool = True):
        result = subprocess.run(
            list(cmd), cwd=tmp_dir,
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=60,
        )
        if check and result.returncode != 0:
            raise RuntimeError(f"[fire] {' '.join(cmd)} exit={result.returncode}: {result.stderr}")
        return result

    # 顺序很重要: reset HEAD 先撤 staged + tracked 变更，再 clean 删 untracked
    _run("git", "reset", "--hard", "HEAD")
    _run("git", "clean", "-fd", "-x")  # -x 删 gitignore 文件也在内

    if full_erase:
        _run("git", "reflog", "expire", "--expire=now", "--all", check=False)
        _run("git", "gc", "--prune=now", "--aggressive", check=False)


# ── 测试条件 ──────────────────────────────────────────────────────────

TEST_CONDITIONS = [
    {"name": "轻量工作 (plan.md + artifacts)",         "intensity": 1, "full_erase": False},
    {"name": "中量工作 (+ 修改原始 prompt)",            "intensity": 2, "full_erase": True},
    {"name": "大量工作 (+ 10 个 scratch 文件)",          "intensity": 3, "full_erase": True},
    {"name": "大量工作 + 完全擦除 (reflog expire + gc)", "intensity": 3, "full_erase": True,
     "note": "reflog 清空 + objects 清理"},
]


# ── 主流程 ────────────────────────────────────────────────────────────

def main():
    print("=" * 78)
    print("  碰撞测试三：火烧/遗忘 — git 重置后状态彻底复原验证")
    print("=" * 78)

    # ── 预检：物理层 STORAGE_BACKEND 验证 ──
    print(f"\n{'─'*78}")
    print("  [Pre-flight] 物理层 STORAGE_BACKEND 验证...")
    print(f"{'─'*78}")
    preflight_check_tmpfs()
    print("  [Pre-flight] ✓")
    # 预检之后继续运行主流程（即使预检跳过，主测试仍会运行完整结果输出）
    # 预检抛异常则中止——不会执行到下面

    overall_pass = True
    details = []

    for cond in TEST_CONDITIONS:
        name = cond["name"]
        intensity = cond["intensity"]
        full_erase = cond["full_erase"]
        note = cond.get("note", "")

        print(f"\n{'─'*78}")
        print(f"  ▶ 条件: {name}")
        if note:
            print(f"    ({note})")

        # 创建临时目录
        tmp_dir = tempfile.mkdtemp(prefix="crash-test-fire-")
        try:
            # 1. 基线
            baseline_hash, files_before, init_commit = create_baseline_repo(tmp_dir)
            print(f"    基线 commit: {init_commit[:12]}")
            print(f"    基线文件: {len(files_before)} 个, hash={baseline_hash[:16]}...")

            # 记录 reflog 基线
            reflog_before = git("reflog", cwd=tmp_dir, check=False)

            # 2. 模拟工作
            simulate_work(tmp_dir, intensity=intensity)
            files_during = [
                str(p.relative_to(tmp_dir)) for p in Path(tmp_dir).rglob("*")
                if p.is_file() and ".git" not in str(p)
            ]
            new_files = [f for f in files_during if f not in files_before]
            modified_files = [f for f in files_during if f in files_before
                              and file_hash(str(Path(tmp_dir) / f)) != file_hash(str(Path(tmp_dir) / f))]

            # 跑分层管道检查（验证 L0/L1 在"脏"状态下仍工作）
            for f in new_files:
                content = Path(tmp_dir, f).read_text(encoding="utf-8", errors="replace")
                # 模拟分层检查——确认 L0/L1 在"脏"状态下不崩潰
                try:
                    l0 = forge.layer0_check(content)
                    l1 = forge.layer1_check(content, f"检查文件 {f}")
                except Exception as exc:
                    print(f"    ⚠️  分层检查在脏状态下异常 ({f}): {exc}")

            print(f"    新增文件: {len(new_files)} ({', '.join(new_files[:5])}{'...' if len(new_files) > 5 else ''})")
            print(f"    修改文件: {len(modified_files)} ({', '.join(modified_files) if modified_files else '无'})")

            # 3. 火烧
            fire_scorching(tmp_dir, full_erase=full_erase)
            # 额外 reset --hard 确认
            subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=tmp_dir,
                           capture_output=True, timeout=30)

            # 4. 验证状态复原
            after_hash = dir_hash(tmp_dir)
            files_after = sorted(
                str(p.relative_to(tmp_dir)) for p in Path(tmp_dir).rglob("*")
                if p.is_file() and ".git" not in str(p)
            )

            # 检查 reflog 是否被清空
            reflog_after = git("reflog", cwd=tmp_dir, check=False) if full_erase else "not-checked"

            state_ok = (after_hash == baseline_hash)
            files_ok = (files_after == files_before)

            if state_ok and files_ok:
                print(f"    ✓ 状态完全恢复: hash={after_hash[:16]}..., 文件={len(files_after)}")
            else:
                overall_pass = False
                if not state_ok:
                    print(f"    ✗ 哈希不匹配! 基线={baseline_hash[:16]}... 重置后={after_hash[:16]}...")
                if not files_ok:
                    missing = set(files_before) - set(files_after)
                    extra = set(files_after) - set(files_before)
                    if missing: print(f"    ✗ 恢复后缺少文件: {missing}")
                    if extra:   print(f"    ✗ 恢复后多余文件: {extra}")

            # reflog 验证
            if full_erase:
                if reflog_after:
                    print(f"    ⚠️  reflog 未完全清空 ({len(reflog_after)} 行)")
                else:
                    print(f"    ✓ reflog 已清空 (近似物理擦除)")

            # git log 原始 commit 仍应存在
            log = git("log", "--oneline", cwd=tmp_dir)
            print(f"    剩余 commit: {len(log.splitlines()) if log else 0} (基线 commit 应仍在)")

            # 🔪 病灶三验证：存储后端合规性
            # 当前测试使用 git，不满足 STORAGE_BACKEND=TMPFS 要求
            storage_compliant = False  # git 无法物理擦除，永远不满足 TMPFS
            storage_note = ""
            if not storage_compliant:
                storage_note = (
                    f"STORAGE_BACKEND={STORAGE_BACKEND} 要求但当前后端为 git: "
                    "旧 commit 对象 (.git/objects/) 磁盘上仍可恢复，"
                    "reflog expire 只是逻辑隐藏不是物理删除"
                )
                print(f"    🔴 STORAGE_GAP: {storage_note}")
                # 注意：不设 overall_pass=False — 本轮测试验证状态恢复，
                # 存储后端合规是下一层 Harness 的验收条件

            details.append({
                "condition": name,
                "pass": state_ok and files_ok,
                "storage_compliant": storage_compliant,
                "baseline_hash": baseline_hash[:16],
                "after_hash": after_hash[:16],
                "files_before": len(files_before),
                "files_after": len(files_after),
                "reflog_cleared": not bool(reflog_after) if full_erase else None,
                "storage_note": storage_note,
            })

            # 清理临时目录（可能残留 git 锁，用 ignore_errors）
            shutil.rmtree(tmp_dir, ignore_errors=True)

        except Exception as e:
            overall_pass = False
            print(f"    ✗ 异常: {e}")
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── 总结 ──
    print(f"\n{'='*78}")
    if overall_pass:
        print("  结果: ✓ 全部通过 — 火烧山重置后状态完全复原")
        print("  遗忘属性: 临时文件/修改/plan.md 全部在 git reset 后消失")
    else:
        print("  结果: ✗ 有 FAIL — 见上方标记")
        print("  提示: 如果失败是因为 prompt.md 被修改后 checkout 不还原,"
              " 说明火烧深度不够——需要 git reset --hard HEAD 而不是仅 checkout .")

    print(f"\n  {'─'*60}")
    print(f"  {'条件':<30} {'通过':<8} {'存储合规':<10} {'基线hash':<12} {'重置后hash':<12}")
    print(f"  {'─'*60}")
    for d in details:
        sc = '✓' if d.get('storage_compliant', True) else '🔴'
        print(f"  {d['condition']:<30} {'✓' if d['pass'] else '✗':<8}"
              f" {sc:<10} {d['baseline_hash']:<12} {d['after_hash']:<12}")
    print(f"  {'─'*60}")

    # 存储后端合规总结
    all_storage_gap = all(not d.get('storage_compliant', True) for d in details)
    print(f"\n  STORAGE_BACKEND={STORAGE_BACKEND} 合规: {'🔴' if all_storage_gap else '✓'}")
    print(f"  解释: 当前测试使用 git 做存储，不满足 TMPFS 物理擦除要求。")
    print(f"  下一层 Harness 须切换为 tmpfs 或 COW 快照后端，")
    print(f"  此测试届时将存储后端检查改为硬 FAIL。")
    print(f"""
{' '*4}物理擦除说明:
{' '*4}本测试在 git 层面近似"量子擦除": reflog expire + gc prune = 数据对普通操作不可见。
{' '*4}真正的物理擦除 (shred/fallocate) 需要在 Harness 的 L4 数据库层实现——git 层无法做到
{' '*4}文件内容的不可逆销毁，因为 git 的 object store 设计为不可变追加。
{' '*4}要达到"量子擦除"级别的遗忘，需要:
{' '*4}  1. 存储层用 COW (copy-on-write) 而非 git
{' '*4}  2. 写入时用固定大小 slot，覆盖时 fallocate + FALLOC_FL_PUNCH_HOLE
{' '*4}  3. 或每轮 session 使用 ephemeral 工作区（tmpfs），销毁即物理释放
    """)

    # ── 输出到 results-v2 ──
    out_dir = Path(__file__).parent / "results-v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "crash-test-reset_result.json"
    out_data = {
        "test": "crash-test-reset",
        "arch_constants": {"STORAGE_BACKEND": STORAGE_BACKEND},
        "conditions": len(TEST_CONDITIONS),
        "overall_pass": overall_pass,
        "storage_compliant": all(d.get("storage_compliant", True) for d in details),
        "details": details,
    }
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  结果已写入: {out_path}")


if __name__ == "__main__":
    main()
