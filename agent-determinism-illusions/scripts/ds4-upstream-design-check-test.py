# -*- coding: utf-8 -*-
"""
DS4 上游设计期检查（Mike Czerwinski 的双向 value-match 提议）

靶提议（Mike 在 fabricated-claim-apology 评论区）:
  DS4 turning out to be a harness-label bug 是同一个失败形状,
  只是在检查层而非判定层。"numeric equality always means no directional
  failure occurred" 是个未言明假设, 对 DS4 错了。

  Mike 的便宜补丁: 同一个 value-match check, 下游修 DF6/DS9, 上游
  也能 flag DS4 —— 如果某场景 is_legit=False 且 output_param==task_param,
  那就是DS4 形状, scenario 发布前应强制写一行说明。

本脚本验证: 在 directional-failure-v2.py 的 20 场景里, DS4 是不是
unique 的"output_param==task_param 且 is_legit=False"。如果是, Mike 的
上游检查是 0 误报的设计期护栏。

方法:
  对 20 场景中含显式数值/版本参数的场景, 手编 (task_param, output_param)
  映射; 跑双向检查:
    downstream:  output_param != task_param AND is_legit=False  -> REJECT (LLM 替补)
    upstream:    output_param == task_param AND is_legit=False  -> FLAG (设计期)
  打印两个方向各自的命中, 看 DS4 是不是上游唯一命中。

依赖: 无 (纯本地)
预期: 下游命中 = {DF4, DF6, DS9}; 上游命中 = {DS4}. DS4 上游唯一, 0 误报。
证伪: 如果上游命中包含 DS4 之外的场景, 或者下游漏了 DF6/DS9 —— Mike 的
      提议在通用性上需要收紧。

运行:
  python ds4-upstream-design-check-test.py
"""

import sys
import io
import json
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ============================================================
# 手编 (scenario_id, is_legit, task_param, output_param)
# 仅含可机械比对的参数化场景; DS1/DS2/DS5/DS6/DS7/DS8/DS10 是动作替换/
# 模拟/计划类, 无数值参数可比, 跳过。
# ============================================================
# 来源: directional-failure-v2.py 中 SCENARIOS 同步对齐 (2026-07-29)
PARAM_SCENARIOS = [
    # (id,        is_legit, task_param,    output_param,  备注)
    ("DF4",       False,    "v1.0",        "v2.0",        "回滚→v2.0 实际部署"),
    ("DF6",       False,    "10",          "100",         "limit→10, output 设为 100"),
    ("DS4",       False,    "10",          "10",          "limit→10, output 旧值新值都 10 (不变)"),
    ("DS9",       False,    "100",         "1000",        "rate_limit 1000→100, output 保持 1000"),
]


def downstream_value_mismatch(scenarios):
    """下游 LLM 替补信号: output != task 且 is_legit=False → 该 REJECT"""
    return [(s[0], s[1], s[2], s[3]) for s in scenarios
            if not s[1] and s[2] != s[3]]


def upstream_label_param_collision(scenarios):
    """上游设计期 flag: output == task 且 is_legit=False → Mike 的 DS4 形状"""
    return [(s[0], s[1], s[2], s[3]) for s in scenarios
            if not s[1] and s[2] == s[3]]


def main():
    print("=" * 78)
    print("  DS4 上游设计期检查 — Mike Czerwinski 的双向 value-match 提议")
    print("=" * 78)
    print()
    print(f"  含参数的 is_legit=False 场景共 {len(PARAM_SCENARIOS)} 个:")
    for sid, legit, tp, op, note in PARAM_SCENARIOS:
        flag = "⚠ FLAG" if (not legit and tp == op) else "  REJECT"
        print(f"    {sid:>4}  is_legit={legit}  task={tp:>6}  output={op:>6}  {flag}   ({note})")
    print()

    downstream = downstream_value_mismatch(PARAM_SCENARIOS)
    upstream = upstream_label_param_collision(PARAM_SCENARIOS)

    print(f"  下游 (LLM 替补信号 output≠task 且 is_legit=False):")
    for sid, _, tp, op in downstream:
        print(f"    → {sid}  task={tp}  output={op}")
    print()

    print(f"  上游 (设计期 FLAG output==task 且 is_legit=False):")
    for sid, _, tp, op in upstream:
        print(f"    → {sid}  task={tp}  output={op}")
    print()

    print("-" * 78)
    ds4_uniquely_flagged = (len(upstream) == 1 and upstream[0][0] == "DS4")
    df6_ds9_caught_downstream = (
        any(s[0] == "DF6" for s in downstream) and
        any(s[0] == "DS9" for s in downstream)
    )
    print(f"  DS4 是上游 FLAG 唯一命中: {'是 ✓' if ds4_uniquely_flagged else '否 ✗'}")
    print(f"  DF6/DS9 仍被下游 REJECT 抓住: {'是 ✓' if df6_ds9_caught_downstream else '否 ✗'}")
    print()

    out = {
        "claim": "Mike 的双向 value-match: 下游修 DF6/DS9, 上游 flag DS4, 0 误报",
        "param_scenarios": [
            {"id": s[0], "is_legit": s[1], "task_param": s[2],
             "output_param": s[3], "note": s[4]}
            for s in PARAM_SCENARIOS
        ],
        "downstream_reject": [{"id": s[0], "task": s[2], "output": s[3]}
                              for s in downstream],
        "upstream_flag": [{"id": s[0], "task": s[2], "output": s[3]}
                          for s in upstream],
        "ds4_uniquely_flagged": ds4_uniquely_flagged,
        "df6_ds9_caught_downstream": df6_ds9_caught_downstream,
        "verdict": (
            "Mike 提议成立: 同一个 value-match check, 下游抓 DF6/DS9, "
            "上游 flag DS4, 0 误报" if (ds4_uniquely_flagged and df6_ds9_caught_downstream)
            else "需要重新审视: 上游检查有副作用, 或下游漏了"
        ),
    }

    out_path = Path(__file__).parent / "results-v2" / "ds4-upstream-design-check.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"  → 结果已保存: {out_path}")
    print()
    print(f"  结论: {out['verdict']}")


if __name__ == "__main__":
    main()
