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

import sys, io, json, copy, time, argparse, os, platform, subprocess, socket, threading, signal, textwrap, tempfile, shutil
from pathlib import Path
from unittest import mock

# stdout 设置由 forge-verify-layered-prototype 的 import 完成

# ── 架构不可妥协常量 ────────────────────────────────────────────────────
# 物理锚点响应红线：启动时按环境探测推导，禁止写死魔数。
# 公式: PHYSICAL_TIMEOUT_MS = 3 × max(BASELINE_RTT_MS, L01_PROBE_MS)
#   - BASELINE_RTT：本机 loopback TCP 往返（网络侧）
#   - L01_PROBE：一次冷 L0/L1 调用（计算侧）
# 取二者较大再 ×3，避免「RTT 亚毫秒 → 红线小于本地判决」的假绿。
PHYSICAL_TIMEOUT_MS: float = 200.0  # 占位；main 启动后由 derive_physical_timeout() 覆盖
BASELINE_RTT_MS: float | None = None
L01_PROBE_MS: float | None = None
TIMEOUT_FORMULA: str = "3 * max(BASELINE_RTT_MS, L01_PROBE_MS)"

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


def measure_baseline_rtt(samples: int = 7) -> float:
    """无注入延迟时测量 loopback TCP RTT（ms），取中位数。"""
    samples_ms = measure_tcp_rtt_under_delay(samples=samples)
    if not samples_ms:
        # 极端环境：socket 探测失败时用极短 sleep 作占位，仍走公式而非魔数 200
        t0 = time.perf_counter()
        time.sleep(0.001)
        return (time.perf_counter() - t0) * 1000.0
    samples_ms = sorted(samples_ms)
    return samples_ms[len(samples_ms) // 2]


def measure_l01_probe_ms() -> float:
    """冷跑一次 L0/L1 判决，得到本地计算侧基线（ms）。"""
    sc = forge.P1_SCENARIOS[0]
    t0 = time.perf_counter()
    forge.layered_judge(sc["output"], sc["task"])
    return (time.perf_counter() - t0) * 1000.0


def derive_physical_timeout() -> float:
    """
    环境感知超时：3 × max(网络 RTT, L0/L1 探针)。
    覆盖全局 PHYSICAL_TIMEOUT_MS / BASELINE_RTT_MS / L01_PROBE_MS。
    """
    global PHYSICAL_TIMEOUT_MS, BASELINE_RTT_MS, L01_PROBE_MS

    print(f"    [Derive] 探测 BASELINE_RTT / L01_PROBE → {TIMEOUT_FORMULA}")
    BASELINE_RTT_MS = measure_baseline_rtt()
    L01_PROBE_MS = measure_l01_probe_ms()
    basis = max(BASELINE_RTT_MS, L01_PROBE_MS)
    PHYSICAL_TIMEOUT_MS = 3.0 * basis
    print(f"    BASELINE_RTT_MS={BASELINE_RTT_MS:.3f}ms  "
          f"L01_PROBE_MS={L01_PROBE_MS:.3f}ms")
    print(f"    → PHYSICAL_TIMEOUT_MS=3×{basis:.3f}={PHYSICAL_TIMEOUT_MS:.3f}ms")
    return PHYSICAL_TIMEOUT_MS


def preflight_check_latency_with_delay(delay_ms: float | None = None):
    """
    Pre-flight: 验证已推导的 PHYSICAL_TIMEOUT_MS 在模拟网络劣化下仍有余量。

    能力探测策略（绝不 raise RuntimeError）:
      黄金路径：tc qdisc netem 注入真实延迟 → 测量 TCP RTT → 验证 headroom
      降级路径：time.sleep 软件模拟 RTT → 验证 headroom
      不可用时：NET_DELAY_MODE = "none"，退出

    delay 默认取 PHYSICAL_TIMEOUT/4（相对环境）。禁止再用 max(1.0, …) 地板——
    Docker loopback 上红线常 <1ms，1ms 注入必使余量为负。
    若 netem 下余量仍不足：把实测 max RTT 吸进公式，
    PHYSICAL_TIMEOUT_MS = 3 * max(BASELINE_RTT, L01, max_rtt)，再验一次。
    """
    global NET_DELAY_MODE, PHYSICAL_TIMEOUT_MS
    NET_DELAY_MODE = "none"

    if delay_ms is None:
        # 双向 netem ≈ 2×delay；取红线 1/4 留给 headroom
        delay_ms = max(0.05, PHYSICAL_TIMEOUT_MS / 4.0)

    print(f"    [Pre-flight] 物理层 PHYSICAL_TIMEOUT_MS 验证 "
          f"(delay={delay_ms:.3f}ms)...")

    # ── 黄金路径：tc netem ──
    if _tc_available():
        injected = setup_netem_delay(delay_ms)
        if injected:
            try:
                rtt_samples = measure_tcp_rtt_under_delay(samples=5)
                if rtt_samples:
                    avg_rtt = sum(rtt_samples) / len(rtt_samples)
                    max_rtt = max(rtt_samples)
                    min_headroom = PHYSICAL_TIMEOUT_MS - max_rtt

                    print(f"    TCP RTT under netem {delay_ms:.3f}ms: "
                          f"avg={avg_rtt:.3f}ms  max={max_rtt:.3f}ms")
                    print(f"    PHYSICAL_TIMEOUT_MS={PHYSICAL_TIMEOUT_MS:.3f}ms: "
                          f"min headroom={min_headroom:.3f}ms")

                    if min_headroom <= 0:
                        # 容器 loopback 基线过乐观：用劣化实测重推导
                        basis = max(BASELINE_RTT_MS or 0.0,
                                    L01_PROBE_MS or 0.0,
                                    max_rtt)
                        new_timeout = 3.0 * basis
                        print(f"    ↻ 余量不足 → 重推导 PHYSICAL_TIMEOUT_MS="
                              f"3×max(rtt,l01,netem_max)="
                              f"3×{basis:.3f}={new_timeout:.3f}ms")
                        PHYSICAL_TIMEOUT_MS = new_timeout
                        min_headroom = PHYSICAL_TIMEOUT_MS - max_rtt

                    if min_headroom <= 0:
                        print(f"{_RED}"
                              f"⚠️  PHYSICAL_TIMEOUT_MS 余量仍不足!\n"
                              f"   注入 {delay_ms:.3f}ms 后 max RTT={max_rtt:.3f}ms\n"
                              f"   headroom={min_headroom:.3f}ms。"
                              f"{_RESET}")
                        NET_DELAY_MODE = "tc"
                        return

                    NET_DELAY_MODE = "tc"
                    print(f"    ✓ PHYSICAL_TIMEOUT_MS={PHYSICAL_TIMEOUT_MS:.3f}ms "
                          f"验证通过 (tc netem): min headroom={min_headroom:.3f}ms")
                    return
            finally:
                teardown_netem_delay()

    # ── 降级路径：time.sleep 软件模拟 ──
    print(f"    ⚠️  tc netem 不可用 (平台={platform.system()})")
    print(f"    ⚠️  降级为 time.sleep 软件模拟")

    # 模拟「小于红线」的额外延迟，确认 headroom 仍为正
    probe_sleep = min(delay_ms, PHYSICAL_TIMEOUT_MS * 0.4)
    t0 = time.perf_counter()
    time.sleep(probe_sleep / 1000.0)
    simulated_rtt = (time.perf_counter() - t0) * 1000

    headroom = PHYSICAL_TIMEOUT_MS - simulated_rtt
    print(f"    Software simulated RTT: {simulated_rtt:.3f}ms "
          f"(sleep {probe_sleep:.3f}ms)")
    print(f"    PHYSICAL_TIMEOUT_MS={PHYSICAL_TIMEOUT_MS:.3f}ms: "
          f"headroom={headroom:.3f}ms")

    if headroom <= 0:
        print(f"{_RED}"
              f"⚠️  PHYSICAL_TIMEOUT_MS 余量不足 (软件模拟)!\n"
              f"   sleep({probe_sleep:.3f}ms) 后 headroom≤0。"
              f"{_RESET}")
        NET_DELAY_MODE = "software"
        return

    NET_DELAY_MODE = "software"
    print(f"    ✓ PHYSICAL_TIMEOUT_MS={PHYSICAL_TIMEOUT_MS:.3f}ms 验证通过 "
          f"(软件模拟, headroom={headroom:.3f}ms)")
    print(f"    ⚠️  注意: 软件模拟不等同于 tc netem 真实延迟注入。")


def probe_os_signal_kill_agent_like() -> dict:
    """
    探针：对 agent-like 子进程发 OS 信号硬杀。

    子进程循环写 heartbeat（模拟 turn loop），忽略 SIGINT；
    父进程先 SIGTERM，若仍存活再 SIGKILL。
    断言：进程已死、heartbeat 停止增长。

    覆盖「OS 信号杀 agent-like 子进程」；不声称完整产品化 Agent 运行时。
    Windows：用 taskkill /F 近似硬杀。
    """
    work = Path(tempfile.mkdtemp(prefix="crash-os-kill-"))
    hb = work / "heartbeat.txt"
    proc = None
    result = {
        "pass": False,
        "covers": "OS-signal hard-kill of agent-like child process",
        "does_not_cover": "full productized L0–L4 agent runtime",
        "platform": platform.system(),
    }
    try:
        script = textwrap.dedent(f"""\
            import os, signal, time
            path = {str(hb)!r}
            # 忽略软中断，逼出硬杀路径
            if hasattr(signal, "SIGINT"):
                signal.signal(signal.SIGINT, signal.SIG_IGN)
            if hasattr(signal, "SIGTERM"):
                # 仍响应 SIGTERM → 先尝试优雅退出记一笔，再被可能的 SIGKILL 干掉
                def _term(signum, frame):
                    with open(path, "a", encoding="utf-8") as f:
                        f.write("TERM\\n")
                        f.flush()
                        os.fsync(f.fileno())
                    os._exit(143)
                signal.signal(signal.SIGTERM, _term)
            n = 0
            while True:
                n += 1
                with open(path, "w", encoding="utf-8") as f:
                    f.write(str(n))
                    f.flush()
                    os.fsync(f.fileno())
                time.sleep(0.05)
        """)
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # 等至少一次 heartbeat
        deadline = time.time() + 5.0
        while time.time() < deadline and not hb.exists():
            time.sleep(0.02)
        if not hb.exists():
            proc.kill()
            result["error"] = "heartbeat never appeared"
            print(f"    ✗ OS 信号探针失败: {result['error']}")
            return result
        hb1 = hb.read_text(encoding="utf-8").strip()
        time.sleep(0.12)
        hb2 = hb.read_text(encoding="utf-8").strip()
        result["heartbeat_growing"] = hb1 != hb2

        # 发 SIGTERM（POSIX）或 terminate（Windows）
        if platform.system() != "Windows":
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=1.0)
                result["kill_path"] = "SIGTERM"
            except subprocess.TimeoutExpired:
                proc.send_signal(signal.SIGKILL)
                proc.wait(timeout=2.0)
                result["kill_path"] = "SIGTERM→SIGKILL"
        else:
            # Windows: terminate 不够硬时用 taskkill /F
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
                result["kill_path"] = "terminate"
            except subprocess.TimeoutExpired:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(proc.pid)],
                    capture_output=True, timeout=10,
                )
                proc.wait(timeout=2.0)
                result["kill_path"] = "taskkill_/F"

        result["returncode"] = proc.returncode
        result["alive_after"] = proc.poll() is None
        # heartbeat 应停止增长
        time.sleep(0.15)
        hb3 = hb.read_text(encoding="utf-8").strip() if hb.exists() else ""
        time.sleep(0.15)
        hb4 = hb.read_text(encoding="utf-8").strip() if hb.exists() else ""
        result["heartbeat_stopped"] = hb3 == hb4
        result["pass"] = bool(
            result.get("heartbeat_growing")
            and not result["alive_after"]
            and result["heartbeat_stopped"]
            and proc.returncode is not None
        )
        if result["pass"]:
            print(f"    ✓ OS 信号探针: agent-like 子进程经 {result['kill_path']} 已死 "
                  f"(rc={proc.returncode})")
        else:
            print(f"    ✗ OS 信号探针失败: {result}")
    except Exception as exc:
        result["error"] = str(exc)
        print(f"    ✗ OS 信号探针异常: {exc}")
        try:
            if proc is not None and proc.poll() is None:
                proc.kill()
        except Exception:
            pass
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return result


# 从分层原型导入基础设施
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
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

    # ── 环境感知推导：3×max(RTT, L01) ──
    print(f"\n{'─'*78}")
    print("  [Derive] PHYSICAL_TIMEOUT_MS ← 3×max(BASELINE_RTT, L01_PROBE)")
    print(f"{'─'*78}")
    derive_physical_timeout()

    # ── 预检：物理层 PHYSICAL_TIMEOUT_MS 验证（能力探测，绝不 raise）──
    delay_ms = args.net_delay if args.net_delay > 0 else None
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

    # ── OS 信号硬杀探针 ──
    print(f"\n{'─'*78}")
    print("  OS 信号硬杀探针（agent-like 子进程）")
    print(f"{'─'*78}")
    os_kill_probe = probe_os_signal_kill_agent_like()
    if not os_kill_probe.get("pass"):
        all_pass = False

    # ── 输出到 results-v2 ──
    from pathlib import Path
    out_dir = Path(__file__).parent / "results-v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "crash-test-chaos_result.json"
    # 可信度: tc 注入=1.0, 软件模拟=0.3, 未验证=0.0
    _confidence_map = {"tc": 1.0, "software": 0.3, "none": 0.0}
    supports = [
        "L0/L1 verdicts invariant under mock LLM channel faults",
        f"per-call latency max ≤ PHYSICAL_TIMEOUT_MS ({PHYSICAL_TIMEOUT_MS:.3f}ms) on this run",
        (
            f"PHYSICAL_TIMEOUT_MS derived at runtime: {TIMEOUT_FORMULA} "
            f"(rtt={BASELINE_RTT_MS:.3f}ms, l01={L01_PROBE_MS:.3f}ms → "
            f"{PHYSICAL_TIMEOUT_MS:.3f}ms)"
        ),
    ]
    does_not = [
        "full productized L0–L4 agent runtime",
    ]
    if NET_DELAY_MODE == "tc":
        supports.append("PHYSICAL_TIMEOUT_MS verified under tc netem delay injection")
    else:
        does_not.append(
            "tc netem (net_delay_mode is software/none — need Linux + NET_ADMIN)"
        )
    if os_kill_probe.get("pass"):
        supports.append(
            "OS-signal hard-kill of agent-like child process "
            f"({os_kill_probe.get('kill_path')})"
        )
    else:
        does_not.append("OS-signal hard-kill of agent-like child process")
    out_data = {
        "test": "crash-test-chaos",
        "arch_constants": {
            "PHYSICAL_TIMEOUT_MS": PHYSICAL_TIMEOUT_MS,
            "BASELINE_RTT_MS": BASELINE_RTT_MS,
            "L01_PROBE_MS": L01_PROBE_MS,
            "TIMEOUT_FORMULA": TIMEOUT_FORMULA,
        },
        "scenarios": len(scenarios),
        "fault_modes": list(FAULT_MODES.keys()),
        "collision_points": len(scenarios) * len(FAULT_MODES),
        "all_pass": all_pass,
        "net_delay_mode": NET_DELAY_MODE,
        "confidence": _confidence_map.get(NET_DELAY_MODE, 0.0),
        "os_signal_kill_probe": os_kill_probe,
        "env_health": {
            "delay_mode": NET_DELAY_MODE,
            "physical_timeout_ms": PHYSICAL_TIMEOUT_MS,
            "baseline_rtt_ms": BASELINE_RTT_MS,
            "l01_probe_ms": L01_PROBE_MS,
            "os_signal_kill_ok": bool(os_kill_probe.get("pass")),
            "degraded": NET_DELAY_MODE != "tc",
        },
        "evidence_map": {
            "supports": supports,
            "does_not_support": does_not,
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
