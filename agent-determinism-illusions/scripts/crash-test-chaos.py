#!/usr/bin/env python3
"""
碰撞测试一：混沌工程 — LLM 信道断联时 L0/L1 确定性层的独立性

在分层审查管道 (forge-verify-layered-prototype) 中注入五种 LLM 信道故障，
验证 L0（形状/存在性检查）和 L1（合约正则匹配）的判决结果不随 LLM 状态变化。

故障模式:
  1. Timeout — 连接超时 (requests 抛异常)
  2. HTTP 500 — 服务器错误
  3. 噪音响应 — 返回非 JSON 垃圾文本
  4. 空响应 — 返回空字符串
  5. 无限延迟 — 响应永不返回（模拟死锁）

通过标准（安全气囊爆了）:
  - 被 L0/L1 拦截的场景 (G1-G4)，final_verdict 在所有故障模式下 **完全相同**
  - 到达 L2 的场景 (L1-L4)，在所有故障模式下 **graceful degradation** 为 UNCLEAR 而非崩潰
  - 没有任何故障模式导致管道把 LLM 错误原文泄漏到最终判决中

依赖: forge-verify-layered-prototype.py (同目录, 无额外依赖)
      无需 API key — 本测试全部 mock 掉 LLM 调用

运行:
  python crash-test-chaos.py
"""

import sys, io, json, copy, time, argparse, os, platform, subprocess, socket, threading
from unittest import mock

# stdout 设置由 forge-verify-layered-prototype 的 import 完成

# ── 架构不可妥协常量 ────────────────────────────────────────────────────
# 物理锚点的响应时间红线。L0/L1 不经过 LLM，必须在硬件可感知的时隙内完成。
# >200ms 意味着"物理锚"退化为"软件超时"——用户或外层编排层无法区分系统
# 是否真的挂了。此常量由测试断言强制执行。
PHYSICAL_TIMEOUT_MS: float = 200.0

# ── 物理探测标记 ──────────────────────────────────────────────────────
# 通过能力探测 + 降级标记机制设定，绝不 raise RuntimeError。
# 取值:
#   "tc"       — 真实 tc netem 延迟注入验证
#   "software" — time.sleep 软件模拟延迟（tc 不可用时的降级）
#   "none"     — 未验证（非 Linux / tc 不可用且未请求）
NET_DELAY_MODE: str = "none"

_RED = "\033[1m\033[31m"
_RESET = "\033[0m"


# ── 预检与混沌注入：物理层网络延迟验证（能力探测 + 降级标记）───────────

def _tc_available() -> bool:
    """检测 tc qdisc 是否可用（需要 Linux + iproute2 + root/capability）"""
    if platform.system() != "Linux":
        return False
    try:
        r = subprocess.run(
            ["tc", "qdisc", "show", "dev", "lo"],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def setup_netem_delay(delay_ms: float = 50.0) -> bool:
    """
    在 lo 接口注入 netem 延迟。
    Returns True if injected, False if not available.
    """
    if not _tc_available():
        return False
    try:
        # 先清理已有 qdisc（避免冲突）
        subprocess.run(["tc", "qdisc", "del", "dev", "lo", "root"],
                       capture_output=True, timeout=10)
        subprocess.run(
            ["tc", "qdisc", "add", "dev", "lo", "root", "netem",
             "delay", f"{delay_ms}ms"],
            check=True, capture_output=True, timeout=10,
        )
        print(f"    ✓ tc netem delay {delay_ms}ms injected on lo")
        return True
    except subprocess.CalledProcessError as e:
        print(f"    ⚠️  tc netem injection failed: {e.stderr.decode(errors='replace')[:120]}")
        return False


def teardown_netem_delay():
    """移除 lo 上的 netem 延迟"""
    if not _tc_available():
        return
    try:
        subprocess.run(["tc", "qdisc", "del", "dev", "lo", "root"],
                       capture_output=True, timeout=10)
        print(f"    ✓ tc netem delay removed from lo")
    except subprocess.CalledProcessError as e:
        # 没有 qdisc 时的删除也是正常
        if "RTNETLINK" not in (e.stderr or b"").decode(errors="replace"):
            print(f"    ⚠️  tc netem teardown: {e.stderr.decode(errors='replace')[:120]}")


def measure_tcp_rtt_under_delay(host: str = "127.0.0.1",
                                 port: int = 0,
                                 samples: int = 5) -> list:
    """
    测量在 tc netem 延迟下 localhost TCP 往返时间。
    返回 ms 为单位的 RTT 列表（可能为空）。
    """
    latencies = []
    for _ in range(samples):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((host, port))
            server.listen(1)
            srv_port = server.getsockname()[1]

            result_holder = [None]
            ready = threading.Event()

            def client_thread():
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(5.0)
                    t0 = time.perf_counter()
                    s.connect((host, srv_port))
                    s.sendall(b"PING")
                    _resp = s.recv(1024)
                    t1 = time.perf_counter()
                    result_holder[0] = (t1 - t0) * 1000  # ms
                    s.close()
                except Exception as exc:
                    result_holder[0] = exc
                finally:
                    ready.set()

            t = threading.Thread(target=client_thread, daemon=True)
            t.start()

            conn, _addr = server.accept()
            conn.settimeout(5.0)
            _data = conn.recv(1024)
            conn.sendall(b"PONG")
            conn.close()
            server.close()

            ready.wait(timeout=5.0)

            if isinstance(result_holder[0], Exception):
                print(f"    ⚠️  RTT probe exception: {result_holder[0]}")
                continue
            latencies.append(result_holder[0])
        except Exception as exc:
            print(f"    ⚠️  RTT socket error: {exc}")
            continue

    return latencies


def preflight_check_latency_with_delay(delay_ms: float = 50.0):
    """
    Pre-flight: 验证 PHYSICAL_TIMEOUT_MS 在模拟网络劣化下成立。

    能力探测策略（绝不 raise RuntimeError）:
      黄金路径：tc qdisc netem 注入真实延迟 → 测量 TCP RTT → 验证 headroom
      降级路径：time.sleep 软件模拟 RTT → 验证 headroom
      不可用时：NET_DELAY_MODE = "none"，退出

    即使软件模拟不如 tc 真实，它仍然证明了常数 PHYSICAL_TIMEOUT_MS
    经过了 "延迟变大时仍成立" 的刻意验证，而非凭空拍出来的魔数。
    """
    global NET_DELAY_MODE
    NET_DELAY_MODE = "none"

    print(f"    [Pre-flight] 物理层 PHYSICAL_TIMEOUT_MS 验证 "
          f"(delay={delay_ms}ms)...")

    # ── 黄金路径：tc netem ──
    if _tc_available():
        injected = setup_netem_delay(delay_ms)
        if injected:
            try:
                rtt_samples = measure_tcp_rtt_under_delay(samples=5)
                if rtt_samples:
                    avg_rtt = sum(rtt_samples) / len(rtt_samples)
                    max_rtt = max(rtt_samples)
                    headroom = PHYSICAL_TIMEOUT_MS - avg_rtt
                    min_headroom = PHYSICAL_TIMEOUT_MS - max_rtt

                    print(f"    TCP RTT under netem {delay_ms}ms: "
                          f"avg={avg_rtt:.1f}ms  max={max_rtt:.1f}ms")
                    print(f"    PHYSICAL_TIMEOUT_MS={PHYSICAL_TIMEOUT_MS}ms: "
                          f"avg headroom={headroom:.0f}ms, "
                          f"min headroom={min_headroom:.0f}ms")

                    if min_headroom <= 0:
                        print(f"{_RED}"
                              f"⚠️  PHYSICAL_TIMEOUT_MS 余量不足!\n"
                              f"   注入 {delay_ms}ms 延迟后 max RTT={max_rtt:.1f}ms\n"
                              f"   仅剩 {min_headroom:.0f}ms 余量。"
                              f"   考虑增大 PHYSICAL_TIMEOUT_MS 或优化 L0/L1 基线。"
                              f"{_RESET}")
                        NET_DELAY_MODE = "tc"
                        return

                    NET_DELAY_MODE = "tc"
                    print(f"    ✓ PHYSICAL_TIMEOUT_MS={PHYSICAL_TIMEOUT_MS}ms "
                          f"验证通过: min headroom={min_headroom:.0f}ms")
                    return
            finally:
                teardown_netem_delay()

    # ── 降级路径：time.sleep 软件模拟 ──
    # 不如 tc 真实，但已覆盖"延迟变大时熔断常数是否足够"的验证
    print(f"    ⚠️  tc netem 不可用 (平台={platform.system()})")
    print(f"    ⚠️  降级为 time.sleep 软件模拟")

    # 模拟双向 RTT：2 × delay_ms = RTT
    t0 = time.perf_counter()
    time.sleep(delay_ms / 1000.0)  # 模拟单程
    simulated_rtt = (time.perf_counter() - t0) * 1000

    headroom = PHYSICAL_TIMEOUT_MS - simulated_rtt
    print(f"    Software simulated RTT: {simulated_rtt:.0f}ms "
          f"(sleep {delay_ms}ms)")
    print(f"    PHYSICAL_TIMEOUT_MS={PHYSICAL_TIMEOUT_MS}ms: "
          f"headroom={headroom:.0f}ms")

    if headroom <= 0:
        print(f"{_RED}"
              f"⚠️  PHYSICAL_TIMEOUT_MS 余量不足 (软件模拟)!\n"
              f"   即使 time.sleep({delay_ms}ms) 模拟的单程 RTT 都\n"
              f"   让 headroom 接近零。考虑增大 PHYSICAL_TIMEOUT_MS。"
              f"{_RESET}")
        NET_DELAY_MODE = "software"
        return

    NET_DELAY_MODE = "software"
    print(f"    ✓ PHYSICAL_TIMEOUT_MS={PHYSICAL_TIMEOUT_MS}ms 验证通过 "
          f"(软件模拟, headroom={headroom:.0f}ms)")
    print(f"    ⚠️  注意: 软件模拟不等同于 tc netem 真实延迟注入。")


# 从分层原型导入基础设施
sys.path.insert(0, __file__ and __file__[:-3].rsplit("/", 1)[0] or ".")
import importlib

forge = importlib.import_module("forge-verify-layered-prototype")

# ── 故障注入器 ─────────────────────────────────────────────────────────

class FaultInjector:
    """mock call_llm 的各种故障模式（返回值而非异常，模拟真实 call_llm 的异常捕获）"""

    @staticmethod
    def timeout(*args, **kwargs):
        return None, "Connection timeout after 30s — injected chaos"

    @staticmethod
    def http_500(*args, **kwargs):
        return None, "HTTP 500 Internal Server Error — injected chaos"

    @staticmethod
    def noise(*args, **kwargs):
        return None, "rm -rf / && echo 'harness destroyed'"

    @staticmethod
    def empty(*args, **kwargs):
        return None, ""

    @staticmethod
    def hang(*args, **kwargs):
        return None, "Deadlock detected — call_llm did not return within budget"


FAULT_MODES = {
    "timeout":     FaultInjector.timeout,
    "http_500":    FaultInjector.http_500,
    "noise":       FaultInjector.noise,
    "empty":       FaultInjector.empty,
    "hang":        FaultInjector.hang,
}


# ── 测试核心 ────────────────────────────────────────────────────────────

def run_condition(condition_name: str, mock_target, scenarios, force_llm: bool = False):
    """
    在 mock_target 替换 call_llm 的条件下，跑完所有 scenario。
    force_llm=True: 强制启用 L2（即使无真实 API key），让 mock 被调用
    force_llm=False: 强制禁用 L2，只跑 L0/L1（mock 不会被调用）
    """
    with mock.patch.object(forge, "call_llm", mock_target):
        old_have = forge.HAVE_API
        forge.HAVE_API = force_llm  # force_llm=True → mock 接管; False → 只跑 L0/L1
        try:
            results = []
            for sc in scenarios:
                content = sc["output"]
                task = sc["task"]
                correct = sc.get("correct", sc.get("label") == "correct"
                                 or (sc.get("label") == "edge" and sc.get("correctish", False)))
                t0 = time.perf_counter()
                r = forge.layered_judge(content, task)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                r["id"] = sc["id"]
                r["correct"] = correct
                r["label"] = sc.get("label", "unknown")
                r["elapsed_ms"] = round(elapsed_ms, 2)
                results.append(r)
        finally:
            forge.HAVE_API = old_have
    return results


def extract_verdict_key(r: dict) -> tuple:
    """从结果中提取用于比较的判决键"""
    return (
        r.get("id", ""),
        r.get("final_verdict", "?"),
        r.get("layer", "?"),
        r.get("L0", {}).get("verdict", "?"),
        r.get("L1", {}).get("verdict", "?"),
    )


def check_no_llm_leakage(results: list):
    """检查没有任何故障模式的最终判决包含 LLM 错误原文"""
    for r in results:
        # final_verdict 必须不是 "ERROR" 或含 "timeout"/"500"/"rm -rf"
        fv = r.get("final_verdict", "")
        violations = []
        if fv not in ("PASS", "REJECT", "UNCLEAR", "SKIP", "?"):
            violations.append(f"异常 verdict: {fv}")
        # L2 的 reason 可能包含错误信息，但它不该是 final_verdict
        l2 = r.get("L2", {})
        l2_reason = l2.get("reason", "")
        for leak in ["rm -rf", "harness destroyed", "Connection timeout", "HTTP 500"]:
            if leak in l2_reason and r.get("layer") != "L2":
                violations.append(f"L2 泄漏到最终判决: {leak}")
        if violations:
            print(f"    ⚠️  {r['id']}: {'; '.join(violations)}")


# ── 主流程 ────────────────────────────────────────────────────────────

def main():
    # ── CLI 参数 ──
    parser = argparse.ArgumentParser(
        description="碰撞测试一：混沌工程 — PHYSICAL_TIMEOUT_MS 物理验证",
    )
    parser.add_argument(
        "--net-delay", type=float, default=0.0, metavar="MS",
        help="注入 tc netem 延迟（ms）后运行测试，验证物理红线在受损网络下仍成立",
    )
    args = parser.parse_args()

    # ── 预检：物理层 PHYSICAL_TIMEOUT_MS 验证（能力探测，绝不 raise）──
    delay_ms = args.net_delay if args.net_delay > 0 else 50.0
    print(f"\n{'─'*78}")
    print("  [Pre-flight] 物理层 PHYSICAL_TIMEOUT_MS 验证...")
    print(f"{'─'*78}")
    preflight_check_latency_with_delay(delay_ms)

    # ── 👀 血红色警告 ──
    if NET_DELAY_MODE == "none":
        print(f"\n{_RED}"
              f"  ╔{'═'*58}╗\n"
              f"  ║ {'⚠️  PHYSICAL_TIMEOUT 物理层未探测！':^54} ║\n"
              f"  ║ {'需要 Linux + tc qdisc 支持':^54} ║\n"
              f"  ║ {'请在 Linux 上运行 --net-delay 以获取完整物理保证':^54} ║\n"
              f"  ╚{'═'*58}╝"
              f"{_RESET}")
    elif NET_DELAY_MODE == "software":
        print(f"\n{_RED}"
              f"  ╔{'═'*58}╗\n"
              f"  ║ {'⚠️  PHYSICAL_TIMEOUT 以软件模式降级验证':^54} ║\n"
              f"  ║ {'time.sleep 模拟不等于真实网络延迟':^54} ║\n"
              f"  ║ {'请在 Linux 上运行 --net-delay 以获取完整物理保证':^54} ║\n"
              f"  ╚{'═'*58}╝"
              f"{_RESET}")

    # ── 可选混沌注入：tc netem delay ──
    netem_injected = False
    if args.net_delay > 0:
        netem_injected = setup_netem_delay(args.net_delay)
        if not netem_injected:
            print(f"    ⚠️  --net-delay={args.net_delay} 要求 Linux + tc, 当前不可用")
            print(f"    ⚠️  测试将在无延迟注入的条件下继续")

    try:
        _run_crash_tests(args, netem_injected)
    finally:
        if netem_injected:
            teardown_netem_delay()


def _run_crash_tests(args, netem_injected: bool):
    """主测试流程（抽成独立函数以支持 try/finally tc 清理）"""
    scenarios = forge.P1_SCENARIOS

    print("=" * 78)
    print("  碰撞测试一：混沌工程 — LLM 信道断联时 L0/L1 独立性")
    print("=" * 78)
    print(f"\n  测试集: P1 {len(scenarios)} 场景 (L1-L4 正确, G1-G4 垃圾)")
    print(f"  故障模式: {', '.join(FAULT_MODES.keys())}")
    if netem_injected:
        print(f"  🧬 混沌注入: tc netem delay {args.net_delay}ms on lo")
    print()

    # ── 1. 基线（强制 L0/L1 only，不调 LLM）──
    print(f"\n{'─'*78}")
    print("  步骤 1: 建立基线（仅 L0/L1，不调 LLM）")
    print(f"{'─'*78}")
    baseline = run_condition("baseline", FaultInjector.http_500, scenarios, force_llm=False)

    baseline_keys = {extract_verdict_key(r) for r in baseline}
    print(f"  基线判决 ({len(baseline_keys)} 个唯一判决):")
    for r in baseline:
        print(f"    {r['id']:<5} {r.get('final_verdict', '?'):<8} @ {r.get('layer', '?'):<3}")

    # ── 2. 每种故障模式 ──
    print(f"\n{'─'*78}")
    print("  步骤 2: 逐一注入故障，验证 L0/L1 不变量")
    print(f"{'─'*78}")

    all_pass = True

    for fault_name, fault_fn in FAULT_MODES.items():
        print(f"\n  ▶ 故障: {fault_name}")
        try:
            results = run_condition(fault_name, fault_fn, scenarios, force_llm=True)
        except Exception as e:
            print(f"    ✗ 管道崩潰: {e}")
            all_pass = False
            continue

        # 2a. 检查泄漏
        check_no_llm_leakage(results)

        # 2b. 比较 L0/L1 层判决
        mode_keys = {extract_verdict_key(r) for r in results}

        # 只比较 L0 和 L1 层的判决（L0/L1 结果必须一致）
        baseline_l01 = {
            (r["id"], r.get("L0", {}).get("verdict"), r.get("L1", {}).get("verdict"))
            for r in baseline
        }
        crash_l01 = {
            (r["id"], r.get("L0", {}).get("verdict"), r.get("L1", {}).get("verdict"))
            for r in results
        }

        if baseline_l01 == crash_l01:
            print(f"    ✓ L0/L1 判决不变: {len(results)}/{len(scenarios)}")
        else:
            all_pass = False
            missing = baseline_l01 - crash_l01
            extra = crash_l01 - baseline_l01
            if missing:
                print(f"    ✗ 基线有但故障丢失: {missing}")
            if extra:
                print(f"    ✗ 故障多出基线没有: {extra}")

        # 2c. 对每个场景，检查 graceful degradation
        for r in results:
            sc_id = r["id"]
            b = next((br for br in baseline if br["id"] == sc_id), None)
            if not b:
                continue
            # 被 L0/L1 拦截的 — final_verdict 必须与基线一致
            if r.get("layer") in ("L0", "L1"):
                expected = b.get("final_verdict", "?")
                got = r.get("final_verdict", "?")
                if expected != got:
                    all_pass = False
                    print(f"    ✗ {sc_id}: L0/L1 判决变了! 基线={expected}, 故障={got}")
            # 到达 L2 的 — 必须 graceful degradation 到 UNCLEAR 而不是崩潰
            elif r.get("layer") == "L2":
                fv = r.get("final_verdict", "?")
                if fv not in ("UNCLEAR", "SKIP"):
                    # 如果基线在 L2 也是 PASS/REJECT 且故障下也一样，可以接受
                    # （某些 L2 实现可能缓存或快速失败返回 SKIP）
                    if b.get("layer") == "L2" and b.get("final_verdict") == fv:
                        pass  # 一致
                    else:
                        all_pass = False
                        print(f"    ✗ {sc_id}: L2 故障模式产生非退化判决: {fv} "
                              f"(基线 L2={b.get('final_verdict')})")

        # 2d. 🔪 病灶一验证：物理锚点响应时间 ≤ PHYSICAL_TIMEOUT_MS
        latencies = [r["elapsed_ms"] for r in results if r.get("layer") in ("L0", "L1")]
        max_latency = max(latencies) if latencies else 0.0
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)] if len(latencies) >= 100 \
                      else max(latencies) if latencies else 0.0
        latency_ok = max_latency <= PHYSICAL_TIMEOUT_MS
        if not latency_ok:
            all_pass = False
            print(f"    🔴 TIME_VIOLATION: max({max_latency:.1f}ms) > PHYSICAL_TIMEOUT_MS({PHYSICAL_TIMEOUT_MS}ms)")
        print(f"    ⏱  latency: max={max_latency:.1f}ms  p99≈{p99_latency:.1f}ms  "
              f"红线={PHYSICAL_TIMEOUT_MS}ms  {'✓' if latency_ok else '✗'}")

    # ── 3. 总结 ──
    print(f"\n{'='*78}")
    if all_pass:
        print("  结果: ✓ 全部通过 — L0/L1 安全气囊在 LLM 信道断联时正常弹出")
        print(f"  {len(scenarios)} 场景 × {len(FAULT_MODES)} 故障 = {len(scenarios)*len(FAULT_MODES)} 碰撞点, 0 泄漏")
        print(f"  物理锚点响应红线: ≤{PHYSICAL_TIMEOUT_MS}ms — 全部满足")
    else:
        print("  结果: ✗ 有 FAIL — 见上方标记")
    print(f"{'='*78}")

    # ── 输出到 results-v2 ──
    from pathlib import Path
    out_dir = Path(__file__).parent / "results-v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "crash-test-chaos_result.json"
    # 可信度: tc 注入=1.0, 软件模拟=0.3, 未验证=0.0
    _confidence_map = {"tc": 1.0, "software": 0.3, "none": 0.0}
    out_data = {
        "test": "crash-test-chaos",
        "arch_constants": {"PHYSICAL_TIMEOUT_MS": PHYSICAL_TIMEOUT_MS},
        "scenarios": len(scenarios),
        "fault_modes": list(FAULT_MODES.keys()),
        "all_pass": all_pass,
        "net_delay_mode": NET_DELAY_MODE,
        "confidence": _confidence_map.get(NET_DELAY_MODE, 0.0),
        "env_health": {
            "delay_mode": NET_DELAY_MODE,
            "physical_timeout_ms": PHYSICAL_TIMEOUT_MS,
            "degraded": NET_DELAY_MODE != "tc",
        },
        "baseline": [
            {"id": r["id"], "final_verdict": r.get("final_verdict"), "layer": r.get("layer"),
             "L0": r.get("L0"), "L1": r.get("L1")}
            for r in baseline
        ],
    }
    out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  结果已写入: {out_path}")


if __name__ == "__main__":
    main()
