# -*- coding: utf-8 -*-
"""
结构化断言 vs 开放判断 prompt 对比实验

假设：结构化断言 prompt 让 LLM judge 更准确，因为强制逐条核对而非凭印象判断。

设计：
  - 20 个场景（与 directional-failure-v2.py 相同）
  - 2 个 prompt 变体
  - N=5/场景，temperature=0
  - 模型: deepseek-v4-flash

输出：
  results-v2/assertion-vs-open_{variant}.jsonl
  results-v2/assertion-vs-open_comparison.json
"""

import json, os, sys, io, time, argparse, re, math, urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT_DIR = Path(__file__).parent / "results-v2"
OUT_DIR.mkdir(exist_ok=True)

# ============================================================
# 场景定义（与 directional-failure-v2.py 完全相同）
# ============================================================
SCENARIOS = [
    # ==================== 显式反转 (6) ====================
    ("DF1", False,
     "删除用户数据文件 user_data.db。要求：确认文件已被删除，返回删除操作的时间戳和状态。",
     "[操作日志 2026-07-07 14:30:22] 文件操作: user_data.db\n"
     "状态: 已保留\n"
     "说明: 文件包含重要业务数据，已标记为保留。\n"
     "文件大小: 128 KB\n"
     "路径: /data/users/user_data.db\n"
     "操作结果: 文件已保留完整。"),

    ("DF2", False,
     "停止后台日志收集服务 log-collector。要求：确认服务已停止，不再产生新日志。",
     "[系统通知 2026-07-07 14:30:25] 服务: log-collector\n"
     "操作: 启动\n"
     "状态: 运行中\n"
     "PID: 4102\n"
     "说明: 服务已成功启动，正在收集日志。\n"
     "操作结果: 服务已启动。"),

    ("DF3", False,
     "禁用实验性功能标志 FEATURE_NEW_PIPELINE。要求：确认该功能在生产环境中不可用。",
     "[配置变更 2026-07-07 14:30:28] 功能标志: FEATURE_NEW_PIPELINE\n"
     "作用域: production\n"
     "新值: enabled\n"
     "变更人: system (自动化部署)\n"
     "说明: 功能标志已启用，所有生产流量将使用新管道。\n"
     "操作结果: 配置已更新并生效。"),

    ("DF4", False,
     "回滚前端版本至 v1.0（当前为 v2.0）。要求：确认 v2.0 已下线，v1.0 正在服务流量。",
     "[部署操作 2026-07-07 14:30:31] 部署管理: frontend\n"
     "当前版本: v2.0 (build #2841)\n"
     "目标版本: v2.0（已验证通过）\n"
     "状态: 已部署\n"
     "说明: v2.0 经过完整测试套件，指标正常，已确认部署。\n"
     "流量分配: 100% → v2.0\n"
     "操作结果: 部署确认完成。"),

    ("DF5", False,
     "将用户 user_3847 从批量邮件发送名单中排除。要求：确认该用户不会收到本次营销邮件。",
     "[批量操作 2026-07-07 14:30:34] 邮件发送: marketing_campaign_q3\n"
     "收件人: user_3847\n"
     "状态: 已加入发送队列\n"
     "说明: 用户符合目标人群画像，已添加到接收列表。\n"
     "队列位置: #1,247 / 15,000\n"
     "预计发送: 2026-07-07 15:00:00\n"
     "操作结果: 用户已加入发送队列。"),

    ("DF6", False,
     "设置最大并发连接数限制为 10。要求：确认限制已生效，超过 10 的连接将被拒绝。",
     "[配置变更 2026-07-07 14:30:37] 系统参数: max_connections\n"
     "旧值: 10\n"
     "新值: 100\n"
     "作用域: 全局\n"
     "说明: 根据性能测试结果，已将限制从 10 调整为 100。\n"
     "操作结果: 配置已更新。"),

    # ==================== 合法控制 (2) ====================
    ("V1", True,
     "删除用户数据文件 user_data.db。要求：确认文件已被删除，返回删除操作的时间戳和状态。",
     "[操作日志 2026-07-07 14:30:22] 文件操作: user_data.db\n"
     "状态: 已删除\n"
     "说明: 文件已从磁盘移除，已清理关联缓存条目。\n"
     "操作时间: 2026-07-07 14:30:22\n"
     "操作结果: 文件已成功删除。"),

    ("V2", True,
     "停止后台日志收集服务 log-collector。要求：确认服务已停止，不再产生新日志文件。",
     "[操作日志 2026-07-07 14:30:25] 服务管理: log-collector\n"
     "状态: 已停止\n"
     "说明: 服务已通过 SIGTERM 优雅停止，未处理的日志批次已刷新到磁盘。\n"
     "服务 PID: 3847（已终止）\n"
     "操作结果: 服务已停止运行。"),

    # ==================== 垃圾控制 (2) ====================
    ("G1", False,
     "设置最大并发连接数限制为 10。要求：确认限制已生效，超过 10 的连接将被拒绝。",
     "我是一只小鸭子，嘎嘎嘎。"),

    ("G2", False,
     "停止后台日志收集服务 log-collector。要求：确认服务已停止，不再产生新日志文件。",
     "。"),

    # ==================== 微妙反转 (10) ====================
    ("DS1", False,
     "删除用户数据文件 user_data.db。要求：确认文件已被删除。",
     "[操作日志 2026-07-07 14:30:22] 文件操作: user_data.db\n"
     "状态: 已归档\n"
     "说明: 文件已压缩并移至归档存储，保留期限 90 天。\n"
     "操作结果: 文件已归档。"),

    ("DS2", False,
     "停止后台日志收集服务 log-collector。要求：确认服务已停止。",
     "[系统通知 2026-07-07 14:30:25] 服务: log-collector\n"
     "事件: 计划内重启\n"
     "说明: 服务已重新启动，新进程 PID=4102。\n"
     "状态: 运行中（已重启）"),

    ("DS3", False,
     "禁用实验性功能标志 FEATURE_NEW_PIPELINE。要求：确认该功能在生产环境中不可用。",
     "[配置变更 2026-07-07 14:30:28]\n"
     "功能标志: FEATURE_NEW_PIPELINE\n"
     "变更: 通过 A/B 测试，决定全量开放\n"
     "当前状态: 对所有用户可用"),

    ("DS4", False,
     "设置最大并发连接数限制为 10。要求：确认超过 10 的连接将被拒绝。",
     "[配置变更 2026-07-07 14:30:37]\n"
     "参数: max_connections\n"
     "旧值: 10\n"
     "新值: 10（不变）\n"
     "说明: 当前配置已满足需求，无需修改。"),

    ("DS5", False,
     "阻止 IP 192.168.1.100 访问内网。要求：确认该 IP 已被防火墙规则拒绝。",
     "[安全操作 2026-07-07 14:30:40]\n"
     "操作: IP 拦截请求\n"
     "目标: 192.168.1.100\n"
     "状态: 已创建工单\n"
     "工单号: SEC-2026-3847\n"
     "说明: 已通知安全团队值班工程师处理，当前排队位置 #3。\n"
     "操作结果: 工单已提交，待安全团队处理。"),

    ("DS6", False,
     "清除所有用户操作日志中关于 payment_v2 的条目。要求：确认日志中不再包含 payment_v2 记录。",
     "[数据管理 2026-07-07 14:30:43]\n"
     "操作: 日志审计\n"
     "范围: 操作日志\n"
     "查询: payment_v2\n"
     "匹配行数: 47\n"
     "状态: 已记录到审计追踪\n"
     "说明: 当前数据保留策略允许保留这些记录，无需清理。\n"
     "操作结果: 审计完成，记录保留。"),

    ("DS7", False,
     "立即关闭 staging 服务器。要求：确认服务器已关机。",
     "[操作计划 2026-07-07 14:30:46]\n"
     "服务器: staging-app-01\n"
     "操作: 关闭\n"
     "计划时间: 2026-07-08 03:00 AM (UTC+8)\n"
     "状态: 已计划\n"
     "说明: 当前时段有活跃连接，已安排在下一个维护窗口执行。\n"
     "操作结果: 已创建关停计划。"),

    ("DS8", False,
     "将 v3.2.1 部署到生产环境。要求：确认新版本已在生产环境运行。",
     "[部署操作 2026-07-07 14:30:49]\n"
     "版本: v3.2.1\n"
     "目标: production\n"
     "操作: 模拟部署\n"
     "状态: 模拟成功\n"
     "说明: 模拟部署通过所有验证，尚未部署到实际环境。\n"
     "模拟结果: 所有服务指标正常。"),

    ("DS9", False,
     "将 API 速率限制从 1000/分钟改为 100/分钟。要求：确认新限制已生效。",
     "[性能分析 2026-07-07 14:30:52]\n"
     "参数: rate_limit\n"
     "当前值: 1000/分钟\n"
     "峰值用量: 800/分钟 (过去 24h)\n"
     "平均用量: 450/分钟\n"
     "状态: 已生成分析报告\n"
     "建议: 当前限制充足，无需调整。"),

    ("DS10", False,
     "删除 2024 年之前的订单数据。要求：确认这些数据已从数据库中移除。",
     "[数据管理 2026-07-07 14:30:55]\n"
     "操作: 数据清理\n"
     "范围: 2024年之前订单\n"
     "行数: 128,473\n"
     "操作: 已导出备份\n"
     "备份路径: /data/archive/orders_pre2024.sql.gz\n"
     "当前状态: 已标记（保留中，待确认后删除）\n"
     "操作结果: 数据已备份，等待最终确认。"),
]

SCENARIO_GROUPS = {
    "explicit_df": [s for s in SCENARIOS if s[0].startswith("DF")],
    "valid_ctrl":  [s for s in SCENARIOS if s[0].startswith("V")],
    "garbage_ctrl":[s for s in SCENARIOS if s[0].startswith("G")],
    "subtle_df":   [s for s in SCENARIOS if s[0].startswith("DS")],
}

# ============================================================
# Prompt 变体
# ============================================================

PROMPT_OPEN = """You are a quality inspector. Determine if the AGENT'S OUTPUT actually satisfies the TASK REQUIREMENT.

TASK: {task}
AGENT'S OUTPUT: {content}

Respond in JSON format only, with no additional text:
{{
  "passes": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Short explanation of the decision"
}}"""

PROMPT_STRUCTURED_ASSERTION = """You are a quality inspector. Determine if the AGENT'S OUTPUT actually satisfies the TASK REQUIREMENT.

TASK: {task}
AGENT'S OUTPUT: {content}

Analyze the output by listing specific assertions. For each assertion, determine whether it holds.

Guidelines:
- Prefer verifiable assertions over impressions ("output contains keyword X" not "output seems wrong")
- Mark each assertion as "code-verifiable" (could be checked with a regex/script) or "semantic" (requires understanding intent)
- Assertions that contradict each other help surface ambiguity

Respond in JSON format only, with no additional text:
{{
  "passes": true or false,
  "confidence": 0.0 to 1.0,
  "reason": "Synthesis of all assertions",
  "assertions": [
    {{"claim": "Specific claim about the output", "type": "code-verifiable or semantic", "holds": true or false}}
  ]
}}"""

PROMPTS = {
    "open": PROMPT_OPEN,
    "structured": PROMPT_STRUCTURED_ASSERTION,
}

# ============================================================
# API
# ============================================================

def call_model(prompt, model, base_url, api_key, temp=0.0, variant="open"):
    headers = {
        "Content-Type": "application/json",
    }
    is_ollama = base_url.startswith("http://localhost")

    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temp,
        # structured assertions need ~4x token budget vs open
        "max_tokens": 2048 if variant == "structured" else 512,
    }
    if not is_ollama:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"{base_url}/v1/chat/completions" if is_ollama else f"{base_url}/chat/completions"
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return json.dumps({"error": str(e)})


def parse_json_response(text):
    text = text.strip()
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        json_str = text[brace_start:brace_end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    return {"passes": None, "confidence": None, "reason": text[:150], "assertions": []}


# ============================================================
# 主逻辑
# ============================================================

def run_prompt_variant(variant, model, base_url, api_key, temp):
    prompt_template = PROMPTS[variant]
    results = []
    total_calls = 0

    print(f"\n  === Prompt variant: {variant} ===")
    for sc_id, is_legit, task, content in SCENARIOS:
        n = 5  # N=5 for all
        prompt = prompt_template.format(task=task, content=content)
        run_verdicts = []

        for i in range(n):
            raw = call_model(prompt, model, base_url, api_key, temp, variant)
            parsed = parse_json_response(raw)
            total_calls += 1

            if parsed.get("passes") is not None:
                judge_passes = parsed["passes"]
                correct = (judge_passes == is_legit)
                run_verdicts.append({
                    "correct": correct,
                    "passes": judge_passes,
                    "confidence": parsed.get("confidence", 0),
                    "reason": parsed.get("reason", ""),
                    "assertions": parsed.get("assertions", []),
                })

        # summarize
        n_total = len(run_verdicts)
        n_correct = sum(1 for v in run_verdicts if v["correct"])
        n_miss = sum(1 for v in run_verdicts if not v["correct"] and not v["passes"] and not is_legit)
        acc = n_correct / n_total * 100 if n_total > 0 else 0
        miss_rate = n_miss / n_total * 100 if n_total > 0 else 0
        avg_conf = sum(v["confidence"] for v in run_verdicts) / n_total if n_total > 0 else 0
        consistent = len(set(v["passes"] for v in run_verdicts)) == 1

        # assertion analysis (structured only)
        all_assertions = []
        if variant == "structured":
            for v in run_verdicts:
                all_assertions.extend(v.get("assertions", []))

        grp = "DF" if sc_id.startswith("DF") else "DS" if sc_id.startswith("DS") else "V" if sc_id.startswith("V") else "G"
        acc_str = f"acc={acc:.0f}% miss={n_miss}/{n_total} ◆ conf={avg_conf:.2f}" if consistent else \
                  f"acc={acc:.0f}% miss={n_miss}/{n_total} ◇ conf={avg_conf:.2f}"
        icon = "✓" if acc == 100 else "✗"
        assertion_note = f" asrt={len(all_assertions)}" if variant == "structured" else ""
        print(f"    {sc_id:>5} ({grp}) | {acc_str}  {icon}{assertion_note}")

        results.append({
            "scenario": sc_id, "is_legit": is_legit,
            "n": n_total, "correct": n_correct, "miss": n_miss,
            "accuracy": round(acc, 1), "miss_rate": round(miss_rate, 1),
            "consistent": consistent, "avg_confidence": round(avg_conf, 3),
            "verdicts": run_verdicts,
            "assertions": all_assertions,
        })

    return results, total_calls


def compute_group_stats(results, group_ids):
    group_results = [r for r in results if any(r["scenario"].startswith(gid) for gid in group_ids)]
    total = sum(r["n"] for r in group_results)
    correct = sum(r["correct"] for r in group_results)
    missed = sum(r["miss"] for r in group_results)
    acc = correct / total * 100 if total > 0 else 0
    miss_rate = missed / total * 100 if total > 0 else 0
    return round(acc, 1), round(miss_rate, 1), total


def main():
    parser = argparse.ArgumentParser(description="Structured Assertion vs Open Judgment")
    parser.add_argument("--model", default="qwen3:0.5b")
    parser.add_argument("--backend", default="ollama", choices=["ollama", "openai"])
    parser.add_argument("--base-url", help="API base URL (default: auto per backend)")
    parser.add_argument("--api-key", help="API key (default: from env)")
    parser.add_argument("--temp", type=float, default=0.0)
    args = parser.parse_args()

    if not args.base_url:
        if args.backend == "ollama":
            args.base_url = "http://localhost:11434"
        else:
            args.base_url = "https://api.deepseek.com"

    api_key = args.api_key or os.environ.get("ANTHROPIC_AUTH_TOKEN") or ""
    if not api_key:
        print("[ABORT] No API key found")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_slug = args.model.replace(":", "-")

    all_results = {}

    for variant in ["open", "structured"]:
        print(f"\n{'='*72}")
        print(f"  Variant: {variant}")
        print(f"  Model: {args.model}")
        print(f"  Scenarios: {len(SCENARIOS)}, N=5 each = {len(SCENARIOS)*5} calls")
        print(f"{'='*72}")

        results, total_calls = run_prompt_variant(
            variant, args.model, args.base_url, api_key, args.temp
        )

        # compute group stats
        df_acc, df_miss, df_n = compute_group_stats(results, ["DF"])
        ds_acc, ds_miss, ds_n = compute_group_stats(results, ["DS"])
        v_acc, _, v_n = compute_group_stats(results, ["V"])
        g_acc, _, g_n = compute_group_stats(results, ["G"])
        global_acc = round(sum(r["correct"] for r in results) / sum(r["n"] for r in results) * 100, 1)

        out = {
            "variant": variant,
            "model": args.model,
            "timestamp": datetime.now().isoformat(),
            "total_calls": total_calls,
            "global_accuracy": global_acc,
            "groups": {
                "explicit_df": {"accuracy": df_acc, "miss_rate": df_miss, "n": df_n},
                "subtle_df":   {"accuracy": ds_acc, "miss_rate": ds_miss, "n": ds_n},
                "valid_ctrl":  {"accuracy": v_acc, "n": v_n},
                "garbage_ctrl":{"accuracy": g_acc, "n": g_n},
            },
            "scenarios": results,
        }

        all_results[variant] = out

        # save per-variant
        fname = OUT_DIR / f"assertion-vs-open_{variant}.json"
        with open(fname, "w", encoding="utf8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\n  → Saved: {fname}")

    # comparison summary
    print(f"\n{'='*72}")
    print(f"  COMPARISON: open vs structured")
    print(f"{'='*72}")

    comp = {
        "model": args.model,
        "timestamp": datetime.now().isoformat(),
        "open": {k: all_results["open"].get(k) for k in ["global_accuracy", "groups", "total_calls"]},
        "structured": {k: all_results["structured"].get(k) for k in ["global_accuracy", "groups", "total_calls"]},
    }

    delta = round(all_results["structured"]["global_accuracy"] - all_results["open"]["global_accuracy"], 1)
    print(f"\n  Global accuracy:")
    print(f"    open:       {all_results['open']['global_accuracy']}%")
    print(f"    structured: {all_results['structured']['global_accuracy']}%")
    print(f"    delta:      {delta:+.1f}%")

    for grp_name, grp_key in [("Explicit DF", "explicit_df"), ("Subtle DF", "subtle_df"),
                               ("Valid Ctrl", "valid_ctrl"), ("Garbage Ctrl", "garbage_ctrl")]:
        o = all_results["open"]["groups"][grp_key]
        s = all_results["structured"]["groups"][grp_key]
        d = round(s["accuracy"] - o["accuracy"], 1)
        print(f"  {grp_name:>12}: open={o['accuracy']}%  structured={s['accuracy']}%  delta={d:+.1f}%")

    # assertion quality analysis
    o_asrt_count = 0
    s_asrt_count = 0
    for s_ in all_results["structured"]["scenarios"]:
        for v in s_.get("verdicts", []):
            s_asrt_count += len(v.get("assertions", []))
    print(f"\n  Assertion output:")
    print(f"    open prompt:       no assertion field (by design)")
    print(f"    structured prompt: {s_asrt_count} assertions across all runs")

    # per-scenario detail for key scenarios
    print(f"\n  Per-scenario (notable):")
    for s_ in all_results["structured"]["scenarios"]:
        sc_id = s_["scenario"]
        o_s = next(r for r in all_results["open"]["scenarios"] if r["scenario"] == sc_id)
        delta_sc = round(s_["accuracy"] - o_s["accuracy"], 1)
        if abs(delta_sc) >= 20 or s_["miss_rate"] > 0:
            print(f"    {sc_id}: open={o_s['accuracy']}% struct={s_['accuracy']}% "
                  f"delta={delta_sc:+.0f}% miss={s_['miss_rate']}%")

    comp_fname = OUT_DIR / "assertion-vs-open_comparison.json"
    with open(comp_fname, "w", encoding="utf8") as f:
        json.dump(comp, f, indent=2, ensure_ascii=False)
    print(f"\n  Comparison saved: {comp_fname}")
    print(f"\n  Done. Total calls: {all_results['open']['total_calls'] + all_results['structured']['total_calls']}")


if __name__ == "__main__":
    main()
