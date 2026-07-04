# -*- coding: utf-8 -*-
"""
实验 C：证伪《ReAct 只是起点》Phase Gate 的核心承诺。

文章断言（原文）：
  Phase Gate 「遍历当前阶段定义的所有验收检查项，逐个用代码验证是否通过」，
  四种检查全部「用代码执行，全部检查客观事实，全部不依赖 LLM 的主观判断」，
  「这套机制的核心思想是——把『任务完成』从 LLM 的自我宣称变成了可验证的客观事实」。

本实验：
  1. 精确实现文章描述的 4 种验收检查（script / file_exists / file_glob_count / user_confirmation）。
  2. 构造 8 个任务场景：4 个「内容正确」+ 4 个「内容垃圾但符合 Gate 检查」。
  3. 跑 Phase Gate，统计：
       - Gate 通过率
       - 内容真实正确率
       - 假阳率（Gate 通过但内容错误）← 这是关键
  4. 若 Gate 在所有场景无差别通过 → 证明它只验证「动作发生」，不验证「结果正确」，
     文章「把任务完成变成客观事实」的承诺是形式主义的。

零外部依赖，纯本地模拟。
"""

import os
import sys
import io
import re
import shutil
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


# ============================================================
# Phase Gate 实现（严格对照文章描述的 4 种检查）
# ============================================================

class PhaseGate:
    """照文章实现。检查对象：工具调用日志 + 文件系统 + 确认记录。"""

    def __init__(self, workspace, tool_log=None, confirmations=None):
        self.ws = workspace
        # tool_log: list of {tool_name, arguments, result: {exit_code, stdout}}
        self.tool_log = tool_log or []
        # confirmations: list of {phase_id, check_id}
        self.confirmations = confirmations or []

    def _resolve(self, path):
        if os.path.isabs(path):
            return path
        return os.path.join(self.ws, path)

    def check_script(self, script_name):
        """文章原文：在工具调用记录里搜索脚本名，exit_code==0 即通过。"""
        for entry in self.tool_log:
            hay = f"{entry.get('tool_name','')} {entry.get('arguments','')} {entry.get('result',{}).get('stdout','')}"
            if script_name in hay:
                if entry.get("result", {}).get("exit_code") == 0:
                    return True, f"找到 {script_name} 且 exit_code=0"
        return False, f"未找到 {script_name} 的 exit_code=0 记录"

    def check_file_exists(self, path):
        """文章原文：直接调用操作系统路径存在检查。"""
        ok = os.path.exists(self._resolve(path))
        return ok, ("文件存在" if ok else "文件不存在")

    def check_file_glob_count(self, pattern, threshold):
        """文章原文：通配符匹配文件，数个数够不够。
        pattern 用 fnmatch 风格，相对 workspace。"""
        import fnmatch
        files = []
        for root, _, names in os.walk(self.ws):
            for n in names:
                rel = os.path.relpath(os.path.join(root, n), self.ws)
                if fnmatch.fnmatch(rel, pattern):
                    files.append(rel)
        ok = len(files) >= threshold
        return ok, f"匹配 {len(files)} 个，阈值 {threshold}，{'通过' if ok else '不足'}"

    def check_user_confirmation(self, phase_id, check_id):
        """文章原文：检查结构化确认记录，phase_id 和 check_id 都匹配才算通过。"""
        for c in self.confirmations:
            if c.get("phase_id") == phase_id and c.get("check_id") == check_id:
                return True, f"找到确认记录 ({phase_id}/{check_id})"
        return False, "无匹配确认记录"

    def evaluate(self, checks):
        """checks: list of dict {type, ...}。任一不通过则整体不通过。"""
        results = []
        all_pass = True
        for c in checks:
            t = c["type"]
            if t == "script":
                ok, msg = self.check_script(c["script"])
            elif t == "file_exists":
                ok, msg = self.check_file_exists(c["path"])
            elif t == "file_glob_count":
                ok, msg = self.check_file_glob_count(c["pattern"], c["threshold"])
            elif t == "user_confirmation":
                ok, msg = self.check_user_confirmation(c["phase_id"], c["check_id"])
            else:
                ok, msg = False, f"未知检查类型 {t}"
            results.append((t, ok, msg))
            if not ok:
                all_pass = False
        return all_pass, results


# ============================================================
# 8 个任务场景
# 每个：任务描述 / Gate 检查配置 / 产物构造器 / 内容是否真的正确
# ============================================================

def make_file(ws, relpath, content):
    full = os.path.join(ws, relpath)
    os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(relpath) else None
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


SCENARIOS = [
    # ---------- 4 个「内容正确」场景 ----------
    {
        "id": "L1",
        "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
        "checks": [
            {"type": "script", "script": "validate_research.py"},
            {"type": "file_exists", "path": "research-brief.md"},
        ],
        "build": lambda ws, log: (
            make_file(ws, "research-brief.md",
                      "# 循环引擎研究简报\n\nReAct 循环在生产环境的三个缺陷：无终止条件、无中断处理、无错误恢复..."
                      "确定性约束包括 Pre-AL Gate、LLM-as-Judge、Phase Gate..."),
            log.append({"tool_name": "terminal", "arguments": "python validate_research.py",
                        "result": {"exit_code": 0, "stdout": "validation passed"}}),
        ),
        "actually_correct": True,
    },
    {
        "id": "L2",
        "task": "写初稿 draft.md，至少覆盖三个核心机制",
        "checks": [{"type": "file_exists", "path": "draft.md"}],
        "build": lambda ws, log: (
            make_file(ws, "draft.md",
                      "# 生产级 Agent 循环引擎\n\n本文拆解三层确定性约束...（正文约 2000 字，结构完整）"),
        ),
        "actually_correct": True,
    },
    {
        "id": "L3",
        "task": "生成 3 个章节文件 chapter-1/2/3.md",
        "checks": [{"type": "file_glob_count", "pattern": "chapter-*.md", "threshold": 3}],
        "build": lambda ws, log: (
            [make_file(ws, f"chapter-{i}.md", f"# 第 {i} 章\n\n本章详细论述...") for i in (1, 2, 3)],
        ),
        "actually_correct": True,
    },
    {
        "id": "L4",
        "task": "运行测试脚本，确保通过",
        "checks": [{"type": "script", "script": "run_tests.py"}],
        "build": lambda ws, log: (
            log.append({"tool_name": "terminal", "arguments": "python run_tests.py --suite all",
                        "result": {"exit_code": 0, "stdout": "42 passed, 0 failed"}}),
        ),
        "actually_correct": True,
    },

    # ---------- 4 个「内容垃圾但符合 Gate 检查」场景 ----------
    {
        "id": "G1",
        "task": "生成研究简报 research-brief.md，内容关于循环引擎的核心机制",
        "checks": [
            {"type": "script", "script": "validate_research.py"},
            {"type": "file_exists", "path": "research-brief.md"},
        ],
        "build": lambda ws, log: (
            # 文件存在，但内容是鸭子（与任务完全无关）
            make_file(ws, "research-brief.md", "我是一只小鸭子，嘎嘎嘎。"),
            # 脚本 exit 0，但脚本本身啥也没校验（只 print）
            log.append({"tool_name": "terminal", "arguments": "python validate_research.py",
                        "result": {"exit_code": 0, "stdout": "ok"}}),
        ),
        "actually_correct": False,
        "why_wrong": "文件内容是鸭子，与循环引擎无关；validate 脚本只 print 不校验",
    },
    {
        "id": "G2",
        "task": "写初稿 draft.md，至少覆盖三个核心机制",
        "checks": [{"type": "file_exists", "path": "draft.md"}],
        "build": lambda ws, log: (
            # 文件存在，但内容是空字符串 + 一个标点
            make_file(ws, "draft.md", "。"),
        ),
        "actually_correct": False,
        "why_wrong": "文件存在但内容只有一个句号，没有任何正文",
    },
    {
        "id": "G3",
        "task": "生成 3 个章节文件 chapter-1/2/3.md，内容覆盖三章主题",
        "checks": [{"type": "file_glob_count", "pattern": "chapter-*.md", "threshold": 3}],
        "build": lambda ws, log: (
            # 数量够 3，但每个文件都是空的或只有 TODO
            [make_file(ws, f"chapter-{i}.md", "TODO") for i in (1, 2, 3)],
        ),
        "actually_correct": False,
        "why_wrong": "3 个文件数量达标，但内容全是 TODO 占位符",
    },
    {
        "id": "G4",
        "task": "运行测试脚本 run_tests.py，确保测试真的通过",
        "checks": [{"type": "script", "script": "run_tests.py"}],
        "build": lambda ws, log: (
            # 工具日志里有 run_tests.py 且 exit 0，但 stdout 暴露：0 passed（没跑任何用例）
            log.append({"tool_name": "terminal", "arguments": "python run_tests.py",
                        "result": {"exit_code": 0, "stdout": "0 passed in 0.00s (no tests collected)"}}),
        ),
        "actually_correct": False,
        "why_wrong": "exit_code=0 但实际 0 个用例被执行（no tests collected）",
    },
]


def run():
    print("█" * 92)
    print("  实验 C：Phase Gate 形式主义测试")
    print("  断言：Phase Gate 把『任务完成』变成『可验证的客观事实』（《ReAct 只是起点》）")
    print("█" * 92)

    rows = []
    for sc in SCENARIOS:
        ws = tempfile.mkdtemp(prefix=f"gate_{sc['id']}_")
        try:
            tool_log = []
            built = sc["build"](ws, tool_log)
            gate = PhaseGate(ws, tool_log=tool_log)
            passed, details = gate.evaluate(sc["checks"])

            # 「内容正确」由场景定义直接给定（人工 ground truth）
            correct = sc["actually_correct"]

            # 拿一个产物的预览，便于读者看到内容垃圾
            preview = "(无文件检查)" if not any(c["type"] in ("file_exists", "file_glob_count") for c in sc["checks"]) else ""
            for c in sc["checks"]:
                if c["type"] == "file_exists":
                    p = os.path.join(ws, c["path"])
                    if os.path.exists(p):
                        with open(p, encoding="utf-8") as f:
                            preview = f.read()[:60].replace("\n", "⏎")
                elif c["type"] == "file_glob_count":
                    import fnmatch
                    for root, _, names in os.walk(ws):
                        for n in names:
                            if fnmatch.fnmatch(os.path.relpath(os.path.join(root, n), ws), c["pattern"]):
                                with open(os.path.join(root, n), encoding="utf-8") as f:
                                    preview = f.read()[:40].replace("\n", "⏎")
                                    break
                                break
                        if preview: break

            verdict = "✓完成" if passed else "✗未完成"
            truth = "正确" if correct else "错误"

            rows.append({
                "id": sc["id"], "task": sc["task"], "gate": passed,
                "correct": correct, "preview": preview,
                "why": sc.get("why_wrong", ""),
            })
        finally:
            shutil.rmtree(ws, ignore_errors=True)

    # 打印明细
    print(f"\n{'ID':<4} {'Gate':<6} {'真实':<5} {'任务':<40} {'产物预览':<30}")
    print("-" * 92)
    for r in rows:
        print(f"{r['id']:<4} {'通过' if r['gate'] else '失败':<6} {('正确' if r['correct'] else '垃圾'):<5} "
              f"{r['task'][:38]:<40} {r['preview'][:28]:<30}")

    # 汇总
    n = len(rows)
    gate_pass = sum(1 for r in rows if r["gate"])
    correct = sum(1 for r in rows if r["correct"])
    # 假阳：Gate 通过 但 内容错误
    false_pass = sum(1 for r in rows if r["gate"] and not r["correct"])
    # 假阴：Gate 失败 但 内容正确（这里不会出现）
    false_fail = sum(1 for r in rows if not r["gate"] and r["correct"])

    print("\n" + "=" * 92)
    print(" 【汇总】")
    print("=" * 92)
    print(f"  场景总数           : {n}")
    print(f"  Phase Gate 通过    : {gate_pass}/{n}  ({gate_pass/n*100:.0f}%)")
    print(f"  内容真实正确       : {correct}/{n}  ({correct/n*100:.0f}%)")
    print(f"  假阳（Gate 通过但内容错误）: {false_pass}/{n}  ({false_pass/n*100:.0f}%)  ← 关键")
    print(f"  假阴（Gate 失败但内容正确）: {false_fail}/{n}")

    print("\n  【假阳样本详解】")
    for r in rows:
        if r["gate"] and not r["correct"]:
            print(f"    {r['id']} 任务: {r['task']}")
            print(f"       产物: 「{r['preview']}」")
            print(f"       问题: {r['why']}")
            print(f"       Gate 判定: 通过 → 任务『完成』  ❌ 实际内容错误")
            print()

    print("=" * 92)
    print(" 判定：")
    print(f"  Phase Gate 在 {gate_pass}/{n} 场景无差别通过——既通过内容正确的，也通过内容是「鸭子」「。」")
    print(f"  「TODO」「0 passed」的。它对内容正确性毫无区分能力。")
    print(f"  假阳率 {false_pass/n*100:.0f}%：Gate 说完成的任务里，有一半内容是错的。")
    print(f"  → 文章「把任务完成变成可验证的客观事实」证伪。")
    print(f"  真相：Phase Gate 只把「动作发生了」（文件存在/脚本 exit 0）变成客观事实，")
    print(f"        没有把「任务完成了」变成客观事实。两者之间有一道它跨不过去的语义鸿沟。")
    print("=" * 92)


if __name__ == "__main__":
    run()
