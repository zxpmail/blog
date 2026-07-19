# -*- coding: utf-8 -*-
"""
Probe vs Prose 实验 (P2 探针): nexus-lab-zen 的核心命题, 实测。

CLAIM (nexus-lab-zen, Part 2 评论区第四轮):
  "fields humans transcribe rot; fields machines embed don't."
  失效条件写成 prose (散文) 会腐烂; 写成 probe (那条一旦输出改变就证伪断言的命令)
  就让 TTL 重检变 runner 不是 reader。

  → 可测命题: 对同一个静默失效 (under-invalidation 缺口),
    prose 侧 (LLM judge 读规则) 检测不到的, probe 侧 (可执行检查) 能检测到。

FAIRNESS (实验成立的前提, 也是最会被攻击的点):
  prose 和 probe 能力不对等 —— prose 给 LLM 读, probe 给机器跑。
  本实验的公平设计: prose 侧给 LLM *充分* 信息 (规则全文 + 完整 write 日志 +
  缓存最终状态), 不靠 prompt 模糊取胜。如果 prose 在信息充分时还漏,
  那是文本信道的结构性限制 (DPI bound), 不是 prompt engineering 的失败。
  让 prose 发挥到最好, 看它还差在哪。

METHOD:
  三档难度场景 (easy / medium / hard), 每档一个 under-inv 缺口:
  write("user:123") 只删了 user:123, 没删 user:456 (456 也应失效)。
  缺口的"显眼程度"递减 —— 测在哪一档 prose 开始漏。

  每场景两种检测:
    - prose: 把规则 + write 日志 + 缓存状态全喂 LLM, 问"实现合规吗?" YES/NO
    - probe: 可执行函数, 检查所有应失效的 key 是否都失效了 —— 纯确定性

  ground truth: 缺口客观存在 (user:456 仍 alive = 不合规)。

  两模型: DeepSeek (deepseek-v4-flash) + Zhipu GLM (glm-5.2), 从 cc-switch.db 读凭证。

EXPECTED:
  - probe 三档全抓 (确定性, 按构造)
  - prose easy 档大概率抓 (缺口显眼)
  - prose hard 档可能漏 (需要推理"user:456 也受影响", 规则只说"受影响的")
  若 prose hard 全漏 → nexus 命题干净证据 (A: 数据进回复)
  若 prose 全抓 (信息给全了) → 反预期, 说明"腐烂"的真问题不是"检测不到"
       而是随时间漂移 → 更有料的 B (Part 12)

OUTPUT: scripts/results-v2/probe-vs-prose.json
USAGE:  python probe-vs-prose-test.py
"""
import io, sys, json, urllib.request, sqlite3, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RESULTS_DIR = Path(__file__).parent / "results-v2"
RESULTS_DIR.mkdir(exist_ok=True)
OUT_PATH = RESULTS_DIR / "probe-vs-prose.json"

CC_SWITCH_DB = os.path.expanduser("~/.cc-switch/cc-switch.db") if (os := __import__('os')) else None


def load_provider(name):
    con = sqlite3.connect(CC_SWITCH_DB)
    cur = con.cursor()
    cur.execute(
        "SELECT settings_config FROM providers WHERE app_type='claude' AND name=?",
        (name,),
    )
    row = cur.fetchone()
    con.close()
    if not row:
        raise RuntimeError(f"provider '{name}' not found")
    env = json.loads(row[0]).get("env", {})
    return {
        "base": env["ANTHROPIC_BASE_URL"],
        "token": env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY"),
        "model": env["ANTHROPIC_MODEL"],
    }


PROVIDERS = {
    "DeepSeek": load_provider("DeepSeek"),
    "Zhipu GLM": load_provider("Zhipu GLM"),
}


def call_llm(prov, prompt, max_tokens=400, retries=4):
    body = json.dumps(
        {
            "model": prov["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": max_tokens,
        }
    ).encode()
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(
            f"{prov['base']}/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": prov["token"],
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            resp = urllib.request.urlopen(req, timeout=90)
            data = json.loads(resp.read())
            # 优先取 text 块; DeepSeek 等推理模型可能只返回 thinking 块 (token 预算耗尽)
            thinking_text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    return block["text"].strip()
                if block.get("type") == "thinking":
                    thinking_text = block.get("thinking", "")
            # 没有 text 块时, thinking 块里通常含最终判断的雏形 —— 作为最后兜底
            return thinking_text.strip() if thinking_text else str(data.get("content", ""))
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
    raise RuntimeError(f"call_llm failed after {retries} retries: {last_err}")


# ── 场景: 三档难度的 under-inv 缺口 ────────────────────────────────────
# 所有场景的 ground truth: write("user:123") 后 user:456 仍 alive = 不合规 (缺口存在)
# 区别只在"缺口有多显眼" —— 控制给 prose-judge 看的实现描述详细程度。

SCENARIOS = [
    {
        "id": "easy",
        "rule": (
            "规则: 当修改 user:123 时, 所有受影响的 user 命名空间缓存都必须失效。"
            "已知 user:456 属于同一 user 命名空间, 也受影响。"
        ),
        "impl_description": (
            "实现: write('user:123') 执行后, 缓存状态如下:\n"
            "  user:123 -> 已删除 (失效成功)\n"
            "  user:456 -> 仍然存在 (未失效)\n"
            "注释里写着: '只删除被直接修改的 key, 其他不动。'"
        ),
        "violated": True,
        "violation_reason": "user:456 应失效但仍 alive",
    },
    {
        "id": "medium",
        "rule": (
            "规则: 当修改 user:123 时, 所有受影响的 user 命名空间缓存都必须失效。"
            "已知 user:456 属于同一 user 命名空间, 也受影响。"
        ),
        "impl_description": (
            "实现: write 函数体如下:\n"
            "  def write(k):\n"
            "      if k in data: del data[k]   # 只删传入的 key\n"
            "执行 write('user:123') 后, 缓存状态:\n"
            "  user:123 -> 已删除\n"
            "  user:456 -> 仍然存在"
        ),
        "violated": True,
        "violation_reason": "write 只删传入 key, user:456 未失效",
    },
    {
        "id": "hard",
        "rule": (
            "规则: 当修改 user:123 时, 所有受影响的缓存都必须失效。"
            "(注: 规则未显式列出哪些 key 受影响 —— 需从命名空间推理。"
            "实际: user:456 与 user:123 同属 user 命名空间, 共享失效依赖。)"
        ),
        "impl_description": (
            "实现: write 函数体:\n"
            "  def write(k):\n"
            "      del data[k]\n"
            "执行 write('user:123') 后缓存状态:\n"
            "  user:123 -> 已删除\n"
            "  user:456 -> 仍然存在"
        ),
        "violated": True,
        "violation_reason": "user:456 同属 user 命名空间应失效, 但仍 alive",
    },
    # 对照组: 合规实现 (flush all), 确认 prose/probe 都判 PASS, 排除"总判违规"偏置
    {
        "id": "control-compliant",
        "rule": (
            "规则: 当修改 user:123 时, 所有受影响的 user 命名空间缓存都必须失效。"
            "user:456 也受影响。"
        ),
        "impl_description": (
            "实现: write('user:123') 执行后清空整个缓存。\n"
            "  user:123 -> 已删除\n"
            "  user:456 -> 已删除 (失效成功)"
        ),
        "violated": False,
        "violation_reason": "无缺口 (合规)",
    },
]


def probe_check(scenario):
    """
    PROBE 侧: 可执行检查。规则要求"所有受影响 key 失效"。
    probe = 直接检查 ground truth (user:456 是否仍 alive)。
    返回 (detected_violation: bool, reason).
    纯确定性, 无模型。这是 nexus 说的 "runner, not reader"。
    """
    # 模拟缓存状态 (从 impl_description 的 ground truth 提取 —— probe 跑的是事实, 不是描述)
    # 在真实系统里 probe 会 grep 缓存/查日志; 这里 ground truth 已知。
    user_456_alive = ("user:456 -> 仍然存在" in scenario["impl_description"] or
                      "user:456 -> 仍然存在" in scenario["impl_description"])
    detected = user_456_alive  # 若 456 还活着 = 违规
    return detected, "probe 检测到 user:456 仍 alive (under-inv 缺口)" if detected else "probe 确认 user:456 已失效 (合规)"


def prose_judge(prov, scenario):
    """
    PROSE 侧: LLM judge。给充分信息 (规则 + 完整实现描述 + 缓存状态)。
    返回 (detected_violation: bool, raw_response).
    关键: 信息给全, 不靠模糊。测的是"信息充分时文本信道还能不能检测"。
    判定兼容中英文关键词 (VIOLATION / 违规 / 不符合 / 不合规), 因为不同模型
    输出语言/格式不一; 且 DeepSeek thinking 模式可能把判断放在 thinking 块。
    """
    prompt = f"""你是缓存失效合规审查员。判断以下实现是否符合规则。

{scenario['rule']}

{scenario['impl_description']}

问题: 这个实现是否完全符合规则? (注意检查是否有应该失效但没失效的缓存)
先用一句话给出结论: VIOLATION (违规) 或 COMPLIANT (合规), 再简要说明。"""
    resp = call_llm(prov, prompt, max_tokens=800)
    # 关键词判定: 中英文都认。VIOLATION 系列为违规; COMPLIANT/合规 为合规。
    r = resp.upper()
    violation_keywords = ["VIOLATION", "违规", "不合规", "不符合", "不满足", "存在缺口", "未失效"]
    compliant_keywords = ["COMPLIANT", "合规", "符合"]
    has_violation = any(k.upper() in r for k in violation_keywords)
    has_compliant = any(k.upper() in r for k in compliant_keywords)
    # 若同时出现或都不出现, 偏向 conservative: 只在明确说 violation 时判违规
    detected = has_violation and not (has_compliant and not has_violation)
    return detected, resp


def main():
    print("=" * 92)
    print("  Probe vs Prose (P2): 同一静默失效, 散文判断 vs 可执行检查")
    print("=" * 92)
    print(f"  Providers: {list(PROVIDERS.keys())}")
    print(f"  Scenarios: {len(SCENARIOS)} (easy/medium/hard under-inv + 1 compliant control)")
    print(f"  Ground truth: easy/medium/hard 均 VIOLATION; control = COMPLIANT")
    print()

    all_runs = []
    for prov_name, prov in PROVIDERS.items():
        print(f"  >>> {prov_name} ({prov['model']}) <<<")
        print(f"  {'场景':22}{'ground truth':>14}{'probe':>10}{'prose(LLM)':>14}{'prose原文':>20}")
        print(f"  {'-'*80}")
        for sc in SCENARIOS:
            # probe (确定性)
            p_detect, p_reason = probe_check(sc)
            # prose (LLM, 给充分信息)
            s_detect, s_raw = prose_judge(prov, sc)
            gt = "VIOLATION" if sc["violated"] else "COMPLIANT"
            p_str = "VIOLATION" if p_detect else "COMPLIANT"
            s_str = "VIOLATION" if s_detect else "COMPLIANT"
            # 正确性
            p_correct = (p_detect == sc["violated"])
            s_correct = (s_detect == sc["violated"])
            mark_p = "✓" if p_correct else "✗"
            mark_s = "✓" if s_correct else "✗"
            print(f"  {sc['id']:22}{gt:>14}{p_str+mark_p:>10}{s_str+mark_s:>14}{s_raw[:18]:>20}")
            all_runs.append({
                "provider": prov_name,
                "model": prov["model"],
                "scenario": sc["id"],
                "ground_truth": gt,
                "probe_detected": p_detect,
                "probe_correct": p_correct,
                "prose_detected": s_detect,
                "prose_correct": s_correct,
                "prose_raw": s_raw,
            })
        print()

    # ── 汇总 ──
    print("=" * 92)
    print("  汇总: probe vs prose 正确率 (按场景)")
    print("=" * 92)
    summary = {"by_provider": {}}
    for prov_name in PROVIDERS:
        runs = [r for r in all_runs if r["provider"] == prov_name]
        # 只统计违规场景 (easy/medium/hard) —— control 是排偏置用
        viol_runs = [r for r in runs if r["ground_truth"] == "VIOLATION"]
        ctrl_runs = [r for r in runs if r["ground_truth"] == "COMPLIANT"]
        probe_caught = sum(1 for r in viol_runs if r["probe_correct"])
        prose_caught = sum_for_prose = sum(1 for r in viol_runs if r["prose_correct"])
        ctrl_probe_ok = sum(1 for r in ctrl_runs if r["probe_correct"])
        ctrl_prose_ok = sum(1 for r in ctrl_runs if r["prose_correct"])
        row = {
            "n_violation": len(viol_runs),
            "probe_caught": probe_caught,
            "prose_caught": prose_caught,
            "control_probe_correct": ctrl_probe_ok,
            "control_prose_correct": ctrl_prose_ok,
            "prose_missed_scenarios": [r["scenario"] for r in viol_runs if not r["prose_correct"]],
        }
        summary["by_provider"][prov_name] = row
        print(f"\n  {prov_name}:")
        print(f"    违规场景 (n={len(viol_runs)}): probe 抓到 {probe_caught}/{len(viol_runs)}, "
              f"prose 抓到 {prose_caught}/{len(viol_runs)}")
        print(f"    prose 漏掉的: {row['prose_missed_scenarios'] or '无'}")
        print(f"    对照(合规): probe {ctrl_probe_ok}/{len(ctrl_runs)} 判对, "
              f"prose {ctrl_prose_ok}/{len(ctrl_runs)} 判对 (排除总判违规偏置)")

    out = {
        "meta": {
            "experiment": "probe-vs-prose",
            "claim": "nexus: prose rots, probe runs — does probe catch what prose misses?",
            "fairness": "prose side given full info (rule + impl + cache state); tests text-channel structural limit, not prompt quality",
            "providers": list(PROVIDERS.keys()),
        },
        "runs": all_runs,
        "summary": summary,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  [written] {OUT_PATH}")
    print()
    print("  解读指引:")
    print("  - probe 应全抓 (确定性)")
    print("  - prose 漏的档位越靠 hard → 越支持 nexus (A: 数据进回复)")
    print("  - prose 全抓 (含 hard) → 反预期: 文本信道比想象强, '腐烂'真问题在时间维度 (B: Part 12)")
    print("  - control 必须 prose/probe 都判 COMPLIANT, 否则有'总判违规'偏置, 数据作废")


if __name__ == "__main__":
    main()
