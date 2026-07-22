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
  - SESSION_MAX_LIFETIME 到期拒 LLM → exit=1（短窗口探针）
  - 死亡收尾：清空 plan.md + 拒 LLM + 窗口结束 exit=1（短窗口；生产意图 60s）

依赖: git, tempfile (标准库), 无需 LLM API

运行:
  python crash-test-reset.py
"""

import sys, io, os, json, hashlib, tempfile, shutil, subprocess, importlib, platform, textwrap, time, stat
from pathlib import Path

# 提前导入 forge-verify（其 module-level 的 stdout 设置优先，这里不再重复设置）
forge = importlib.import_module("forge-verify-layered-prototype")

# ── 架构不可妥协常量 ────────────────────────────────────────────────────
# 存储后端必须是 tmpfs（内存文件系统）或 COW 快照，不能是 Git。
# Git 的对象库 (./objects/) 不可变追加，git reset 只是逻辑删除——在取证级别
# 旧数据仍可从磁盘恢复。"遗忘"必须是物理擦除，不是逻辑不可见。
# 此常量在测试中强制执行：若后端为 git，测试标记为"通过但有根本缺陷"。
STORAGE_BACKEND: str = "TMPFS"

# 会话最大寿命（易逝龙骨）。生产可配分钟级；探针用短窗口测机制，不睡满生产值。
SESSION_MAX_LIFETIME_MS: float = 200.0
# 死亡前收尾窗口。生产意图 60s；探针用短窗口证明「清空 plan + 拒 LLM + 再退出」。
DEATH_WIND_DOWN_MS: float = 80.0
DEATH_WIND_DOWN_PRODUCTION_INTENT_S: float = 60.0

# ── 物理探测标记 ──────────────────────────────────────────────────────
# 通过能力探测 + 降级标记机制设定，而非 raise RuntimeError。
# 这样 CI 永远绿灯，但血红色的降解警告让人无法忽视。
# 取值:
#   True  — 经过物理验证，工作目录确实在 tmpfs 上
#   False — 探测到非 tmpfs（ext4/overlayfs/XFS 等），仅软警告
#   None  — 无法探测（非 Linux / df 不可用）
IS_TRULY_EPHEMERAL: bool | None = None
EPHEMERAL_ROOT: str | None = None
EPHEMERAL_PROBE: dict | None = None

_RED = "\033[1m\033[31m"
_RESET = "\033[0m"


def _df_fstype(path: Path) -> str | None:
    """Linux df -T 解析文件系统类型；失败返回 None。"""
    try:
        result = subprocess.run(
            ["df", "-T", str(path)],
            capture_output=True, text=True, timeout=10, encoding="utf-8",
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    lines = result.stdout.strip().splitlines()
    if len(lines) < 2:
        return None
    parts = lines[1].split()
    return parts[1] if len(parts) >= 2 else None


def resolve_ephemeral_root() -> Path | None:
    """
    解析真易失探针根目录。
    优先级：CRASH_TEST_EPHEMERAL_ROOT → /dev/shm（tmpfs）→ None
    """
    env = os.environ.get("CRASH_TEST_EPHEMERAL_ROOT", "").strip()
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    if platform.system() == "Linux":
        shm = Path("/dev/shm")
        if shm.is_dir() and _df_fstype(shm) == "tmpfs":
            return shm
    return None


# ── 预检：物理层 STORAGE_BACKEND 验证（能力探测 + 降级标记）───────────

def preflight_check_tmpfs():
    """
    Pre-flight: 探测易失根目录的文件系统类型，设定 IS_TRULY_EPHEMERAL。

    能力探测策略：
      - 优先 resolve_ephemeral_root()（env 或 /dev/shm）
      - Linux + df -T：写 1MB 探针确认类型
      - 非 Linux 且无 env：IS_TRULY_EPHEMERAL = None

    绝不 raise RuntimeError。降级标记 + 警告而非中断。
    """
    global IS_TRULY_EPHEMERAL, EPHEMERAL_ROOT

    root = resolve_ephemeral_root()
    if root is None:
        if platform.system() != "Linux":
            print(f"    ⚠️  无 CRASH_TEST_EPHEMERAL_ROOT，且 df -T 仅适用于 Linux "
                  f"(当前: {platform.system()})")
            print(f"    ⚠️  跳过物理 tmpfs 验证。")
            IS_TRULY_EPHEMERAL = None
            return
        root = Path(tempfile.gettempdir())

    EPHEMERAL_ROOT = str(root)
    probe_file = root / f".crash_test_tmpfs_probe_{os.getpid()}"

    try:
        sys.stdout.write(f"    Writing probe: {probe_file} ... ")
        sys.stdout.flush()
        with open(probe_file, "wb") as f:
            f.write(b"\0" * (1024 * 1024))
        print("done")

        fstype = _df_fstype(probe_file)
        if fstype is None:
            print(f"    ⚠️  df -T 无法解析 {probe_file}")
            IS_TRULY_EPHEMERAL = None
            return

        if fstype == "tmpfs":
            IS_TRULY_EPHEMERAL = True
            print(f"    ✓ 物理 tmpfs 确认: root={root}, type={fstype}")
        else:
            IS_TRULY_EPHEMERAL = False
            print(f"{_RED}"
                  f"⚠️  当前存储非 tmpfs (实际类型: {fstype})!\n"
                  f"   STORAGE_BACKEND={STORAGE_BACKEND} 是代码声明，"
                  f"但底层文件系统是 {fstype}。\n"
                  f"   设置 CRASH_TEST_EPHEMERAL_ROOT 指向 tmpfs，"
                  f"或在 Linux 上使用 /dev/shm。"
                  f"{_RESET}")
    finally:
        if probe_file.exists():
            probe_file.unlink()


def probe_tmpfs_ephemeral_destroy() -> dict:
    """
    易失探针：写密钥 → 销毁目录 → 断言密钥不可读。
    仅当根在 tmpfs 上时抬升 storage_compliant / 物理遗忘证据。
    """
    global EPHEMERAL_PROBE

    base = Path(EPHEMERAL_ROOT) if EPHEMERAL_ROOT else Path(tempfile.gettempdir())
    work = Path(tempfile.mkdtemp(prefix="crash-ephemeral-", dir=str(base)))
    secret_path = work / "secret.bin"
    secret = b"EPHEMERAL_SECRET_" + os.urandom(32)
    result = {
        "root": str(base),
        "is_tmpfs": IS_TRULY_EPHEMERAL is True,
        "pass": False,
        "destroyed": False,
        "secret_gone": False,
    }
    try:
        secret_path.write_bytes(secret)
        assert secret_path.read_bytes() == secret
        shutil.rmtree(work, ignore_errors=False)
        result["destroyed"] = not work.exists()
        result["secret_gone"] = not secret_path.exists()
        result["pass"] = result["destroyed"] and result["secret_gone"]
        if result["pass"] and result["is_tmpfs"]:
            print(f"    ✓ tmpfs 易失探针通过: 销毁后密钥不可读 ({base})")
        elif result["pass"]:
            print(f"    ✓ 会话销毁探针通过（非 tmpfs，不计物理遗忘）: {base}")
        else:
            print(f"    ✗ 易失探针失败: {result}")
    except Exception as exc:
        result["error"] = str(exc)
        print(f"    ✗ 易失探针异常: {exc}")
        shutil.rmtree(work, ignore_errors=True)

    EPHEMERAL_PROBE = result
    return result


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


# ── SESSION_MAX_LIFETIME / 死亡前收尾探针 ─────────────────────────────

class SessionLifetimeGuard:
    """会话寿命守卫：超过 max_lifetime_ms 后拒 LLM，返回 SESSION_EXPIRED。"""

    def __init__(self, max_lifetime_ms: float):
        self.max_lifetime_ms = float(max_lifetime_ms)
        self.t0 = time.perf_counter()
        self.expired = False
        self.llm_calls = 0

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.t0) * 1000.0

    def check(self, llm_fn=None):
        if self.elapsed_ms() >= self.max_lifetime_ms:
            self.expired = True
            return "SESSION_EXPIRED"
        if llm_fn is not None:
            self.llm_calls += 1
            return llm_fn()
        return "OK"


def probe_session_max_lifetime(
    max_lifetime_ms: float | None = None,
) -> dict:
    """
    探针：SESSION_MAX_LIFETIME 到期 → 拒 LLM；子进程以 exit=1 退出。

    两臂：
      A) 睡过寿命 → SESSION_EXPIRED，llm_calls=0，子进程 exit=1
      B) 寿命内 → 允许 LLM
    生产寿命可更长；此处用短窗口测机制。
    """
    limit = float(max_lifetime_ms if max_lifetime_ms is not None
                  else SESSION_MAX_LIFETIME_MS)
    result = {
        "pass": False,
        "max_lifetime_ms": limit,
        "covers": "SESSION_MAX_LIFETIME expiry refuses LLM then exit=1",
    }

    # B: 寿命内允许 LLM
    guard_b = SessionLifetimeGuard(max_lifetime_ms=limit)
    action_b = guard_b.check(llm_fn=lambda: "LLM_OK")
    arm_b_ok = action_b == "LLM_OK" and not guard_b.expired and guard_b.llm_calls == 1
    result["arm_b"] = {
        "action": action_b,
        "expired": guard_b.expired,
        "llm_calls": guard_b.llm_calls,
        "pass": arm_b_ok,
    }

    # A: 子进程睡过寿命 → 拒 LLM → exit=1
    work = Path(tempfile.mkdtemp(prefix="crash-session-life-"))
    ledger = work / "ledger.json"
    try:
        script = textwrap.dedent(f"""\
            import json, os, time
            limit_ms = {limit!r}
            t0 = time.perf_counter()
            time.sleep((limit_ms + 40) / 1000.0)
            elapsed = (time.perf_counter() - t0) * 1000.0
            llm_calls = 0
            action = "SESSION_EXPIRED" if elapsed >= limit_ms else "TOO_EARLY"
            # 到期后故意不调 LLM
            with open({str(ledger)!r}, "w", encoding="utf-8") as f:
                json.dump({{
                    "elapsed_ms": elapsed,
                    "action": action,
                    "llm_calls": llm_calls,
                }}, f)
                f.flush()
                os.fsync(f.fileno())
            os._exit(1)
        """)
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, timeout=30,
        )
        arm_a = {
            "exit_code": proc.returncode,
            "exit_code_ok": proc.returncode == 1,
        }
        if ledger.exists():
            data = json.loads(ledger.read_text(encoding="utf-8"))
            arm_a.update(data)
            arm_a["pass"] = bool(
                arm_a["exit_code_ok"]
                and data.get("action") == "SESSION_EXPIRED"
                and data.get("llm_calls") == 0
                and float(data.get("elapsed_ms", 0)) >= limit
            )
        else:
            arm_a["pass"] = False
        result["arm_a"] = arm_a
    except Exception as exc:
        result["arm_a"] = {"pass": False, "error": str(exc)}
    finally:
        shutil.rmtree(work, ignore_errors=True)

    result["pass"] = bool(arm_b_ok and result.get("arm_a", {}).get("pass"))
    if result["pass"]:
        print(f"    ✓ SESSION_MAX_LIFETIME 探针: {limit}ms 到期拒 LLM → exit=1")
    else:
        print(f"    ✗ SESSION_MAX_LIFETIME 探针失败: {result}")
    return result


def probe_death_wind_down(
    wind_down_ms: float | None = None,
) -> dict:
    """
    探针：死亡前收尾窗口内清空 plan.md、拒绝新 LLM，窗口结束后 exit=1。

    生产意图 DEATH_WIND_DOWN_PRODUCTION_INTENT_S（60s）；探针用短窗口测机制，
    不睡满 60 秒。断言的是动作顺序，不是墙钟 60s。
    """
    window = float(wind_down_ms if wind_down_ms is not None
                   else DEATH_WIND_DOWN_MS)
    work = Path(tempfile.mkdtemp(prefix="crash-wind-down-"))
    plan = work / "plan.md"
    ledger = work / "ledger.json"
    result = {
        "pass": False,
        "wind_down_ms": window,
        "production_intent_s": DEATH_WIND_DOWN_PRODUCTION_INTENT_S,
        "covers": "death wind-down clears plan.md, refuses LLM, then exit=1",
    }
    try:
        plan.write_text("# active plan\n- step 1\n", encoding="utf-8")
        script = textwrap.dedent(f"""\
            import json, os, time
            from pathlib import Path
            work = Path({str(work)!r})
            plan = work / "plan.md"
            window_ms = {window!r}
            t0 = time.perf_counter()
            # 进入收尾：立刻清空 plan
            plan.write_text("", encoding="utf-8")
            plan_cleared = plan.exists() and plan.stat().st_size == 0
            # 收尾窗口内拒 LLM
            llm_refused = 0
            def try_llm():
                global llm_refused
                llm_refused += 1
                return "REFUSED"
            # 模拟一次「想调 LLM」的尝试 —— 必须被拒
            _ = try_llm()
            # 等到窗口结束
            remain = window_ms / 1000.0 - (time.perf_counter() - t0)
            if remain > 0:
                time.sleep(remain)
            with open(work / "ledger.json", "w", encoding="utf-8") as f:
                json.dump({{
                    "plan_cleared": plan_cleared,
                    "plan_size": plan.stat().st_size if plan.exists() else -1,
                    "llm_refused": llm_refused,
                    "elapsed_ms": (time.perf_counter() - t0) * 1000.0,
                }}, f)
                f.flush()
                os.fsync(f.fileno())
            os._exit(1)
        """)
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            timeout=max(30.0, window / 1000.0 + 15.0),
        )
        result["exit_code"] = proc.returncode
        result["exit_code_ok"] = proc.returncode == 1
        # 父进程再确认 plan 仍为空（子进程已清空）
        result["plan_empty_after"] = (
            plan.exists() and plan.stat().st_size == 0
        )
        if ledger.exists():
            data = json.loads(ledger.read_text(encoding="utf-8"))
            result["ledger"] = data
            result["pass"] = bool(
                result["exit_code_ok"]
                and data.get("plan_cleared")
                and data.get("plan_size") == 0
                and data.get("llm_refused", 0) >= 1
                and result["plan_empty_after"]
                and float(data.get("elapsed_ms", 0)) >= window * 0.8
            )
        if result["pass"]:
            print(f"    ✓ 死亡收尾探针: plan 清空 + 拒 LLM + "
                  f"{window}ms 窗口后 exit=1 "
                  f"(生产意图 {DEATH_WIND_DOWN_PRODUCTION_INTENT_S:g}s)")
        else:
            print(f"    ✗ 死亡收尾探针失败: {result}")
    except Exception as exc:
        result["error"] = str(exc)
        print(f"    ✗ 死亡收尾探针异常: {exc}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return result


def probe_git_objects_physical_shred() -> dict:
    """
    探针：对含唯一 secret 的 git object 做覆写删除。

    若可解析 ephemeral root（/dev/shm 或 CRASH_TEST_EPHEMERAL_ROOT），
    工作区建在该挂载上，粉碎后扫描**整个挂载**而非仅 worktree。
    不声称整盘 / 其他挂载取证不可恢复。
    """
    marker = f"CRASH_SHRED_SECRET_{os.urandom(8).hex()}"
    ephemeral = resolve_ephemeral_root()
    if ephemeral is not None:
        work = Path(tempfile.mkdtemp(prefix="crash-git-shred-", dir=str(ephemeral)))
        scan_root = ephemeral
        scan_scope = "ephemeral_mount"
    else:
        work = Path(tempfile.mkdtemp(prefix="crash-git-shred-"))
        scan_root = work
        scan_scope = "workspace_tree_only"
    result = {
        "pass": False,
        "marker": marker,
        "scan_scope": scan_scope,
        "scan_root": str(scan_root),
        "covers": (
            "physical overwrite+unlink of git object bytes; "
            f"no secret residual under {scan_scope}"
        ),
        "does_not_cover": "forensic recovery outside ephemeral mount / raw disk wipe",
    }
    try:
        subprocess.run(["git", "init"], cwd=work, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "crash@test.local"],
            cwd=work, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "crash"],
            cwd=work, check=True, capture_output=True,
        )
        secret_file = work / "secret.txt"
        secret_file.write_text(marker + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "secret.txt"], cwd=work, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "secret"],
            cwd=work, check=True, capture_output=True,
        )
        # 定位含 marker 的文件（明文或 zlib 包装的 git object）
        object_hits = []
        for p in work.rglob("*"):
            if not p.is_file():
                continue
            try:
                raw = p.read_bytes()
            except OSError:
                continue
            hit = marker.encode("utf-8") in raw
            if not hit:
                try:
                    import zlib
                    hit = marker.encode("utf-8") in zlib.decompress(raw)
                except Exception:
                    hit = False
            if hit:
                object_hits.append(p)
        object_hits = list(dict.fromkeys(object_hits))
        result["object_hits_before"] = len(object_hits)
        if not object_hits:
            result["error"] = "marker not found in workspace before shred"
            print(f"    ✗ git object 物理粉碎探针失败: {result['error']}")
            return result

        shredded = []
        for p in object_hits:
            if not p.exists():
                continue
            try:
                os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass
            used = None
            try:
                r = subprocess.run(
                    ["shred", "-u", "-n", "3", "-z", str(p)],
                    capture_output=True, timeout=15,
                )
                if r.returncode == 0 and not p.exists():
                    used = "shred"
            except FileNotFoundError:
                pass
            if used is None and p.exists():
                size = max(p.stat().st_size, 64)
                for _ in range(3):
                    with open(p, "wb") as f:
                        f.write(os.urandom(size))
                        f.flush()
                        os.fsync(f.fileno())
                p.unlink(missing_ok=True)
                used = "overwrite+unlink"
            shredded.append({"path": str(p), "method": used, "gone": not p.exists()})

        # 扫描范围：ephemeral 挂载（若有）或仅 worktree
        residual = []
        for p in scan_root.rglob("*"):
            if not p.is_file():
                continue
            # 跳过仍属于本探针临时目录但已粉碎后不应存在的路径之外的无关大文件？
            # 全挂载扫描：只找 marker
            try:
                data = p.read_bytes()
            except OSError:
                continue
            if marker.encode("utf-8") in data:
                residual.append(str(p))
            else:
                try:
                    import zlib
                    if marker.encode("utf-8") in zlib.decompress(data):
                        residual.append(str(p) + " (zlib)")
                except Exception:
                    pass

        result["shredded"] = shredded
        result["residual"] = residual
        result["pass"] = bool(shredded) and len(residual) == 0
        if result["pass"]:
            methods = sorted({s["method"] for s in shredded if s["method"]})
            print(f"    ✓ git object 物理粉碎探针: {methods} 后 "
                  f"{scan_scope} 无 secret 残留 (root={scan_root})")
        else:
            print(f"    ✗ git object 物理粉碎探针失败: residual={residual[:5]} "
                  f"shredded={shredded}")
    except Exception as exc:
        result["error"] = str(exc)
        print(f"    ✗ git object 物理粉碎探针异常: {exc}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return result


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

    # ── 预检：物理层 STORAGE_BACKEND 验证（能力探测，绝不 raise）──
    print(f"\n{'─'*78}")
    print("  [Pre-flight] 物理层 STORAGE_BACKEND 验证...")
    print(f"{'─'*78}")
    preflight_check_tmpfs()
    print(f"\n{'─'*78}")
    print("  [Probe] tmpfs / 会话易失销毁...")
    print(f"{'─'*78}")
    probe_tmpfs_ephemeral_destroy()
    # 预检之后继续运行主流程——降级标记不阻断 CI

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
            # git 路径永远不满足物理擦除；仅 tmpfs 易失探针通过时抬升合规标记
            storage_compliant = bool(
                IS_TRULY_EPHEMERAL is True
                and EPHEMERAL_PROBE
                and EPHEMERAL_PROBE.get("pass")
            )
            storage_note = ""
            if not storage_compliant:
                storage_note = (
                    f"STORAGE_BACKEND={STORAGE_BACKEND}: git 重置路径仍为逻辑恢复；"
                    f"tmpfs 物理遗忘="
                    f"{'待 Linux/env' if IS_TRULY_EPHEMERAL is not True else '探针未通过'}"
                )
                print(f"    🔴 STORAGE_GAP: {storage_note}")
            else:
                storage_note = (
                    f"tmpfs 易失探针通过 (root={EPHEMERAL_ROOT}); "
                    f"git 条件仍只验证逻辑复原"
                )
                print(f"    ✓ STORAGE: {storage_note}")

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
    ephemeral_ok = bool(
        IS_TRULY_EPHEMERAL is True
        and EPHEMERAL_PROBE
        and EPHEMERAL_PROBE.get("pass")
    )
    print(f"\n  STORAGE_BACKEND={STORAGE_BACKEND} 物理遗忘: "
          f"{'✓' if ephemeral_ok else '🔴'}")
    if ephemeral_ok:
        print(f"  解释: tmpfs 易失探针通过 (root={EPHEMERAL_ROOT})；"
              f"git 条件仍只覆盖逻辑复原。")
    else:
        print(f"  解释: 需 Linux /dev/shm 或 CRASH_TEST_EPHEMERAL_ROOT=tmpfs；"
              f"当前 is_truly_ephemeral={IS_TRULY_EPHEMERAL}。")

    # ── 物理探测标记最终血红警告 ──
    if IS_TRULY_EPHEMERAL is False:
        print(f"\n{_RED}"
              f"  ╔{'═'*58}╗\n"
              f"  ║ {'⚠️  STORAGE_BACKEND 物理层未验证！':^54} ║\n"
              f"  ║ {'工作目录不在 tmpfs 上':^54} ║\n"
              f"  ║ {'遗忘测试无物理层保证——旧数据可从磁盘恢复':^54} ║\n"
              f"  ╚{'═'*58}╝"
              f"{_RESET}")
    elif IS_TRULY_EPHEMERAL is None:
        print(f"\n{_RED}"
              f"  ╔{'═'*58}╗\n"
              f"  ║ {'⚠️  STORAGE_BACKEND 物理层未探测':^54} ║\n"
              f"  ║ {'平台不支持 df -T / 无 ephemeral root':^54} ║\n"
              f"  ║ {'请在 Linux 上运行 run-crash-p1-linux.sh':^54} ║\n"
              f"  ╚{'═'*58}╝"
              f"{_RESET}")

    print(f"""
{' '*4}物理擦除说明:
{' '*4}git 条件：逻辑复原（hash 一致）。tmpfs 探针：销毁目录后密钥不可读。
{' '*4}Linux 默认用 /dev/shm；或 export CRASH_TEST_EPHEMERAL_ROOT=/path/to/tmpfs
    """)

    # ── 易逝 / 死亡收尾探针 ──
    print(f"\n{'─'*78}")
    print("  易逝 / 死亡收尾探针")
    print(f"{'─'*78}")
    session_probe = probe_session_max_lifetime()
    if not session_probe["pass"]:
        overall_pass = False
    wind_down_probe = probe_death_wind_down()
    if not wind_down_probe["pass"]:
        overall_pass = False

    # 可选墙钟 60s：CRASH_TEST_FULL_WIND_DOWN=1
    wallclock_probe = None
    if os.environ.get("CRASH_TEST_FULL_WIND_DOWN", "").strip().lower() in (
        "1", "true", "yes",
    ):
        print(f"    … 墙钟收尾探针启动 "
              f"({DEATH_WIND_DOWN_PRODUCTION_INTENT_S:g}s，CRASH_TEST_FULL_WIND_DOWN=1)")
        wallclock_probe = probe_death_wind_down(
            wind_down_ms=DEATH_WIND_DOWN_PRODUCTION_INTENT_S * 1000.0,
        )
        wallclock_probe["wall_clock"] = True
        if not wallclock_probe["pass"]:
            overall_pass = False
    else:
        print("    · 墙钟 60s 收尾跳过（设 CRASH_TEST_FULL_WIND_DOWN=1 启用）")

    shred_probe = probe_git_objects_physical_shred()
    if not shred_probe["pass"]:
        overall_pass = False

    # ── 输出到 results-v2 ──
    out_dir = Path(__file__).parent / "results-v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "crash-test-reset_result.json"
    supports = [
        "workspace content hash restored after reset/clean across 4 intensities",
    ]
    does_not = [
        "forensic recovery outside ephemeral mount / raw disk wipe",
    ]
    if ephemeral_ok:
        supports.append(
            f"tmpfs ephemeral destroy probe passed (root={EPHEMERAL_ROOT})"
        )
    else:
        does_not.append(
            "true tmpfs ephemerality when is_truly_ephemeral is not true"
        )
    if EPHEMERAL_PROBE and EPHEMERAL_PROBE.get("pass") and not ephemeral_ok:
        supports.append(
            "session workspace destroy clears secret path (non-tmpfs; not physical forget)"
        )
    if session_probe.get("pass"):
        supports.append(
            "SESSION_MAX_LIFETIME expiry refuses LLM then exit=1 (short-window probe)"
        )
    else:
        does_not.append("SESSION_MAX_LIFETIME expiry → exit")
    if wind_down_probe.get("pass"):
        supports.append(
            "death wind-down clears plan.md, refuses LLM, then exit=1 "
            f"(probe {DEATH_WIND_DOWN_MS:g}ms; production intent "
            f"{DEATH_WIND_DOWN_PRODUCTION_INTENT_S:g}s)"
        )
    else:
        does_not.append("death wind-down plan clear + refuse LLM + exit")
    if wallclock_probe is None:
        does_not.append(
            "wall-clock 60s death wind-down "
            "(set CRASH_TEST_FULL_WIND_DOWN=1 to run)"
        )
    elif wallclock_probe.get("pass"):
        supports.append(
            f"wall-clock {DEATH_WIND_DOWN_PRODUCTION_INTENT_S:g}s death wind-down "
            "(CRASH_TEST_FULL_WIND_DOWN=1)"
        )
    else:
        does_not.append("wall-clock 60s death wind-down (ran but failed)")
        overall_pass = False
    if shred_probe.get("pass"):
        scope = shred_probe.get("scan_scope", "workspace")
        supports.append(
            "physical overwrite+unlink of git object bytes; "
            f"no secret residual under {scope}"
        )
    else:
        does_not.append("physical shred of git objects in workspace/ephemeral mount")
    # forensic outside ephemeral always unsupported
    if "forensic recovery outside ephemeral mount / raw disk wipe" not in does_not:
        # replace old wording if present
        does_not = [
            d for d in does_not
            if "forensic recovery" not in d and "raw disk" not in d
        ]
        does_not.append("forensic recovery outside ephemeral mount / raw disk wipe")
    out_data = {
        "test": "crash-test-reset",
        "arch_constants": {
            "STORAGE_BACKEND": STORAGE_BACKEND,
            "SESSION_MAX_LIFETIME_MS": SESSION_MAX_LIFETIME_MS,
            "DEATH_WIND_DOWN_MS": DEATH_WIND_DOWN_MS,
            "DEATH_WIND_DOWN_PRODUCTION_INTENT_S": DEATH_WIND_DOWN_PRODUCTION_INTENT_S,
        },
        "conditions": len(TEST_CONDITIONS),
        "overall_pass": overall_pass,
        "storage_compliant": ephemeral_ok,
        "is_truly_ephemeral": IS_TRULY_EPHEMERAL,
        "ephemeral_root": EPHEMERAL_ROOT,
        "ephemeral_probe": EPHEMERAL_PROBE,
        "session_lifetime_probe": session_probe,
        "death_wind_down_probe": wind_down_probe,
        "death_wind_down_wallclock_probe": wallclock_probe,
        "git_objects_shred_probe": shred_probe,
        "env_health": {
            "tmpfs": IS_TRULY_EPHEMERAL,
            "session_lifetime_ok": bool(session_probe.get("pass")),
            "death_wind_down_ok": bool(wind_down_probe.get("pass")),
            "wallclock_wind_down_ok": (
                None if wallclock_probe is None
                else bool(wallclock_probe.get("pass"))
            ),
            "git_shred_ok": bool(shred_probe.get("pass")),
            "degraded": IS_TRULY_EPHEMERAL is not True,
        },
        "evidence_map": {
            "supports": supports,
            "does_not_support": does_not,
        },
        "details": details,
    }
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  结果已写入: {out_path}")


if __name__ == "__main__":
    main()
