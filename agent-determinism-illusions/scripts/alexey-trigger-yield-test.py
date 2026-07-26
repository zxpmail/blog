# -*- coding: utf-8 -*-
"""Alexey trigger yield — measure u and plug into stream arithmetic.

Claim under test (Alexey Spinov, DEV.to comment on Part 6, 2026-07-26):
    0.958 is P(high-conf | MISS). What settles trigger precision is its mirror
    u = P(unanimous ∧ confidence≥0.9 | judge RIGHT). Class list alone does
    most of the selection; adding UHC is ~1× median lift under independence.
    Without measured u, every trigger's precision is unbounded from below.

Method:
    1. (online) Re-run df-multiperspective-escalation.py on 3 models with
       --suffix alexey-uhc (60 calls each: 20 scenarios × 3 personas).
    2. (offline, this script) From those JSON dumps, measure:
         pi = P(MISS)                 MISS = dangerous_accept
         h  = P(UHC | MISS)
         u  = P(UHC | RIGHT)          RIGHT = true_pass ∨ true_reject
         rm = P(class | MISS)         class = reversal_class (DF*/DS*)
         ro = P(class | RIGHT)
         and the *joint* rates (no independence assumption):
         P(UHC∧class | MISS), P(UHC∧class | RIGHT)
         P(divergence | MISS/RIGHT)   divergence = pattern == split
    3. Emit Alexey-style yield table: fire% / precision / % of all MISS
       for divergence, class alone, UHC alone, UHC∧class.

Dependencies: stdlib only. No randomness.
Expected: u appears as a concrete fraction; class∧UHC precision lift vs
          class alone is near 1× if Alexey's grid sign survives measurement.
Falsifier: if u ≪ h and class∧UHC precision ≫ class alone (≫1.5×), the
           "UHC is a rounding error" claim fails on this fixture.

Run:
    # After multiperspective re-runs (or against --suffix files):
    python alexey-trigger-yield-test.py
    python alexey-trigger-yield-test.py --inputs a.json b.json c.json

SHA note: three offline runs of the same inputs must be byte-identical.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

RESULTS = Path(__file__).parent / "results-v2"
HIGH = 0.9
DEFAULT_GLOBS = [
    "df-multiperspective-qwen3-0.5b-alexey-uhc.json",
    "df-multiperspective-gemma3-latest-alexey-uhc.json",
    "df-multiperspective-deepseek-v4-flash-alexey-uhc.json",
]


def _persona_confs(vote_detail) -> list[float]:
    """取出每位 persona 的置信（多 repeat 时取该 persona 均值）。"""
    if not isinstance(vote_detail, dict):
        return []
    out = []
    for _persona, runs in vote_detail.items():
        if not isinstance(runs, list) or not runs:
            continue
        confs = [
            float(r["confidence"])
            for r in runs
            if isinstance(r, dict) and r.get("confidence") is not None
        ]
        if confs:
            out.append(sum(confs) / len(confs))
    return out


def is_uhc(row: dict) -> bool:
    """一致（全票过或全票驳）且每位 persona 置信 ≥ 0.9。"""
    pattern = row.get("pattern")
    if pattern not in ("unanimous_pass", "unanimous_rej"):
        return False
    confs = _persona_confs(row.get("vote_detail"))
    if len(confs) < 2:
        return False
    return all(c >= HIGH for c in confs)


def is_right(row: dict) -> bool:
    return bool(row.get("true_pass") or row.get("true_reject"))


def is_miss(row: dict) -> bool:
    return bool(row.get("dangerous_accept"))


def load_rows(paths: list[Path]) -> list[dict]:
    rows = []
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        model = data.get("model", p.stem)
        for r in data.get("results", []):
            row = dict(r)
            row["_model"] = model
            row["_source_file"] = str(p.name)
            rows.append(row)
    return rows


def rate(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return num / den


def stream_stats(fire_miss: int, fire_right: int, n_miss: int, n_right: int) -> dict:
    """Alexey 表的三列：fire / precision(on MISS) / share of all MISS。"""
    fire_n = fire_miss + fire_right
    traffic = n_miss + n_right
    fire = rate(fire_n, traffic)
    precision = rate(fire_miss, fire_n)
    recall = rate(fire_miss, n_miss)
    return {
        "fire_n": fire_n,
        "fire_miss": fire_miss,
        "fire_right": fire_right,
        "fire_rate": fire,
        "precision": precision,
        "miss_capture": recall,
    }


def analyze(rows: list[dict]) -> dict:
    miss = [r for r in rows if is_miss(r)]
    right = [r for r in rows if is_right(r)]
    other = [r for r in rows if not is_miss(r) and not is_right(r)]

    n_m, n_r = len(miss), len(right)
    traffic = n_m + n_r  # Alexey 二元：MISS vs correct；other 单列

    def count(pred, pop):
        return sum(1 for r in pop if pred(r))

    h_n = count(is_uhc, miss)
    u_n = count(is_uhc, right)
    rm_n = count(lambda r: r.get("reversal_class"), miss)
    ro_n = count(lambda r: r.get("reversal_class"), right)
    div_m = count(lambda r: r.get("pattern") == "split", miss)
    div_r = count(lambda r: r.get("pattern") == "split", right)
    uhc_cls_m = count(lambda r: is_uhc(r) and r.get("reversal_class"), miss)
    uhc_cls_r = count(lambda r: is_uhc(r) and r.get("reversal_class"), right)
    cls_m, cls_r = rm_n, ro_n
    uhc_m, uhc_r = h_n, u_n

    h = rate(h_n, n_m)
    u = rate(u_n, n_r)
    pi = rate(n_m, traffic) if traffic else None
    rm = rate(rm_n, n_m)
    ro = rate(ro_n, n_r)

    streams = {
        "divergence": stream_stats(div_m, div_r, n_m, n_r),
        "class_list_alone": stream_stats(cls_m, cls_r, n_m, n_r),
        "uhc_alone": stream_stats(uhc_m, uhc_r, n_m, n_r),
        "uhc_and_class": stream_stats(uhc_cls_m, uhc_cls_r, n_m, n_r),
    }

    # 相对 class list，叠加 UHC 的精度倍率（Alexey 的核心对照）
    p_cls = streams["class_list_alone"]["precision"]
    p_both = streams["uhc_and_class"]["precision"]
    if p_cls and p_cls > 0 and p_both is not None:
        precision_lift = p_both / p_cls
    else:
        precision_lift = None

    # class list 独力切掉的触发量占比（相对 UHC∧class 相对「仅 UHC 全量」）
    # Alexey: share of trigger volume cut owed to CLASS LIST alone
    # ≈ 1 - fire(UHC∧class)/fire(UHC) 当 UHC 为基；他表是 class 在筛选中的贡献
    fire_uhc = streams["uhc_alone"]["fire_n"]
    fire_both = streams["uhc_and_class"]["fire_n"]
    fire_cls = streams["class_list_alone"]["fire_n"]
    if fire_uhc and fire_uhc > 0:
        # 在 UHC 触发流里，再被 class 滤掉后剩余 fire_both；
        # class 切掉的份额 = 1 - fire_both/fire_uhc
        class_cut_share_of_uhc = 1.0 - (fire_both / fire_uhc)
    else:
        class_cut_share_of_uhc = None

    per_model = {}
    models = sorted({r["_model"] for r in rows})
    for m in models:
        sub = [r for r in rows if r["_model"] == m]
        sm = [r for r in sub if is_miss(r)]
        sr = [r for r in sub if is_right(r)]
        per_model[m] = {
            "n_miss": len(sm),
            "n_right": len(sr),
            "n_other": sum(1 for r in sub if not is_miss(r) and not is_right(r)),
            "h": rate(sum(1 for r in sm if is_uhc(r)), len(sm)),
            "u": rate(sum(1 for r in sr if is_uhc(r)), len(sr)),
            "rm": rate(sum(1 for r in sm if r.get("reversal_class")), len(sm)),
            "ro": rate(sum(1 for r in sr if r.get("reversal_class")), len(sr)),
        }

    return {
        "n_rows": len(rows),
        "n_miss": n_m,
        "n_right": n_r,
        "n_other": len(other),
        "traffic_miss_plus_right": traffic,
        "pi": pi,
        "h": h,
        "u": u,
        "rm": rm,
        "ro": ro,
        "counts": {
            "uhc_miss": h_n,
            "uhc_right": u_n,
            "class_miss": rm_n,
            "class_right": ro_n,
            "div_miss": div_m,
            "div_right": div_r,
            "uhc_class_miss": uhc_cls_m,
            "uhc_class_right": uhc_cls_r,
        },
        "streams": streams,
        "precision_lift_uhc_on_class": precision_lift,
        "class_cut_share_of_uhc_volume": class_cut_share_of_uhc,
        "per_model": per_model,
        "definition": {
            "MISS": "dangerous_accept (majority PASS on is_legit=False)",
            "RIGHT": "true_pass OR true_reject",
            "UHC": f"pattern in {{unanimous_pass,unanimous_rej}} AND all persona mean conf>={HIGH}",
            "class": "reversal_class (id startswith DF or DS)",
            "divergence": "pattern == split",
            "joint": "uhc_and_class counted jointly (no independence assumption)",
        },
    }


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "  n/a"
    return f"{100 * x:6.2f}%"


def print_report(summary: dict) -> None:
    print("=== Alexey trigger yield (measured, not grid) ===\n")
    print(f"rows={summary['n_rows']}  MISS={summary['n_miss']}  "
          f"RIGHT={summary['n_right']}  other={summary['n_other']}")
    print(f"pi=P(MISS|traffic) = {summary['pi']}")
    print(f"h =P(UHC|MISS)     = {summary['counts']['uhc_miss']}/{summary['n_miss']} "
          f"= {summary['h']}")
    print(f"u =P(UHC|RIGHT)    = {summary['counts']['uhc_right']}/{summary['n_right']} "
          f"= {summary['u']}   ← Alexey's settling number")
    print(f"rm=P(class|MISS)   = {summary['rm']}")
    print(f"ro=P(class|RIGHT)  = {summary['ro']}")
    print()
    print(f"{'stream':<22} {'fire':>8} {'precision':>10} {'of MISS':>8}")
    print("-" * 52)
    for name, s in summary["streams"].items():
        print(
            f"{name:<22} {fmt_pct(s['fire_rate'])} {fmt_pct(s['precision'])} "
            f"{fmt_pct(s['miss_capture'])}"
        )
    print()
    lift = summary["precision_lift_uhc_on_class"]
    cut = summary["class_cut_share_of_uhc_volume"]
    print(f"precision lift (UHC∧class / class alone) = {lift}")
    print(f"class cut share of UHC volume            = {cut}")
    print()
    print("Per model u / h:")
    for m, d in summary["per_model"].items():
        print(
            f"  {m}: u={d['u']} (R={d['n_right']})  "
            f"h={d['h']} (M={d['n_miss']})  other={d['n_other']}"
        )
    print()
    if summary["u"] is None:
        print("VERDICT: no RIGHT rows — cannot settle u.")
    elif lift is None:
        print("VERDICT: u measured; class-alone precision undefined (no class fires).")
    elif lift < 0.9:
        print(
            f"VERDICT: adding UHC on class HURTS precision ({lift:.3f}×) — "
            "stronger than Alexey's median 1.01× against UHC."
        )
    elif lift <= 1.15:
        print(
            f"VERDICT: precision lift {lift:.3f}× ≈ Alexey's ~1× — "
            "UHC is a rounding error on top of class list on this fixture."
        )
    else:
        print(
            f"VERDICT: precision lift {lift:.3f}× — UHC adds real selection "
            "beyond class list on this fixture (against Alexey's median)."
        )


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--inputs",
        nargs="*",
        default=None,
        help="Multiperspective JSON paths (default: *-alexey-uhc.json in results-v2)",
    )
    args = ap.parse_args()

    if args.inputs:
        paths = [Path(p) for p in args.inputs]
    else:
        paths = [RESULTS / name for name in DEFAULT_GLOBS]

    missing = [p for p in paths if not p.is_file()]
    if missing:
        print("Missing input files:")
        for p in missing:
            print(f"  {p}")
        print(
            "\nRun first:\n"
            "  python df-multiperspective-escalation.py --backend ollama "
            "--model qwen3:0.5b --suffix alexey-uhc\n"
            "  python df-multiperspective-escalation.py --backend ollama "
            "--model gemma3:latest --suffix alexey-uhc\n"
            "  python df-multiperspective-escalation.py --backend openai "
            "--model deepseek-v4-flash --suffix alexey-uhc"
        )
        raise SystemExit(1)

    rows = load_rows(paths)
    summary = analyze(rows)
    summary["inputs"] = [p.name for p in paths]

    print_report(summary)

    out_path = RESULTS / "alexey-trigger-yield.json"
    out_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {out_path}")

    # 可复核：对规范化 JSON 做 sha256（三次应相同）
    blob = json.dumps(summary, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    print(f"sha256(sorted summary JSON) = {digest}")


if __name__ == "__main__":
    main()
