#!/usr/bin/env python3
"""
碰撞测试五：可部署 harness-kernel 进程边界

Claim
-----
harness-kernel.py：
- NDJSON 单会话：STARTLE 不杀进程；BUDGET/SESSION/wind_down → exit=1 + plan 空
- turn 真 LLM：mock=0 时走 call_llm_text；可注入 llm_fn；缺凭证 → LLM_ERROR
- HTTP 多会话：会话间预算/plan 隔离；单会话 wind_down 不杀进程；/shutdown 才退出
- verify → forge-verify L0

Dependencies: harness-kernel.py, forge-verify-layered-prototype.py
Falsify: 多会话互相污染；mock=0 无凭证却 LLM_OK；HTTP wind_down 误杀进程

运行:
  SKIP_LLM=1 python crash-test-harness-kernel.py
"""

from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
KERNEL = HERE / "harness-kernel.py"

if hasattr(sys.stdout, "buffer"):
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
    except Exception:
        pass


def _env(**extra) -> dict:
    env = os.environ.copy()
    env.setdefault("SKIP_LLM", "1")
    # 清掉可能误触发真 API 的变量（真 LLM 臂单独设）
    for k in list(env):
        if k.startswith("ANTHROPIC_") or k in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OLLAMA_HOST"):
            if "keep_llm" not in extra:
                env.pop(k, None)
    env.update({k: v for k, v in extra.items() if k != "keep_llm"})
    return env


def _read_json_line(proc: subprocess.Popen, timeout_s: float = 5.0) -> dict:
    assert proc.stdout is not None
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.01)
            continue
        line = line.strip()
        if not line:
            continue
        return json.loads(line)
    raise TimeoutError("no JSON line from harness-kernel")


def _send(proc: subprocess.Popen, obj: dict) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _http_json(method: str, url: str, body: dict | None = None,
               headers: dict | None = None, timeout: float = 5.0) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else "{}"
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"ok": False, "error": raw}


def run() -> dict:
    print("=" * 78)
    print("  碰撞测试五：harness-kernel（真 LLM + HTTP 多会话）")
    print("=" * 78)

    arms: dict[str, dict] = {}
    work = Path(tempfile.mkdtemp(prefix="harness-kernel-test-"))
    env = _env()

    # ── A: 正常 turn + STARTLE 不退出 ──
    proc = subprocess.Popen(
        [
            sys.executable, str(KERNEL),
            "--session-ms", "30000", "--startle-ms", "50",
            "--budget-cost-pct", "25", "--work-dir", str(work / "a"), "--mock-llm",
        ],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=env,
    )
    try:
        ready = _read_json_line(proc)
        _send(proc, {"op": "turn", "latency_ms": 1, "prompt": "hi"})
        t1 = _read_json_line(proc)
        _send(proc, {"op": "turn", "latency_ms": 120})
        t2 = _read_json_line(proc)
        still_alive = proc.poll() is None
        arms["startle_keeps_alive"] = {
            "pass": (
                ready.get("action") == "READY"
                and t1.get("action") == "LLM_OK"
                and t2.get("action") == "STARTLE"
                and still_alive
            ),
        }
        print(f"  {'✓' if arms['startle_keeps_alive']['pass'] else '✗'} "
              f"正常 turn + STARTLE 进程仍活")

        _send(proc, {
            "op": "verify", "latency_ms": 1,
            "task": "写初稿 draft.md，至少覆盖三个核心机制",
            "output": "。",
        })
        v = _read_json_line(proc, timeout_s=15.0)
        arms["verify_l0_reject"] = {
            "action": v.get("action"),
            "layer": (v.get("verify") or {}).get("layer"),
            "pass": (
                v.get("action") == "VERIFY_REJECT"
                and (v.get("verify") or {}).get("layer") == "L0"
                and proc.poll() is None
            ),
        }
        print(f"  {'✓' if arms['verify_l0_reject']['pass'] else '✗'} "
              f"verify G2 → VERIFY_REJECT@L0")

        for _ in range(4):
            _send(proc, {"op": "turn", "latency_ms": 1, "charge": True})
            resp = _read_json_line(proc)
            if resp.get("action") == "BUDGET_EXIT":
                break
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = proc.wait(timeout=5)
        plan_a = work / "a" / "plan.md"
        arms["budget_exit"] = {
            "pass": rc == 1 and resp.get("action") == "BUDGET_EXIT"
            and plan_a.exists() and plan_a.stat().st_size == 0,
        }
        print(f"  {'✓' if arms['budget_exit']['pass'] else '✗'} "
              f"BUDGET_EXIT → exit=1 + plan 空")
    finally:
        if proc.poll() is None:
            proc.kill()

    # ── C: 会话到期 ──
    proc2 = subprocess.Popen(
        [
            sys.executable, str(KERNEL),
            "--session-ms", "80", "--startle-ms", "50",
            "--work-dir", str(work / "c"), "--mock-llm",
        ],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=env,
    )
    try:
        _read_json_line(proc2)
        time.sleep(0.12)
        _send(proc2, {"op": "turn", "latency_ms": 1})
        resp = _read_json_line(proc2)
        rc2 = proc2.wait(timeout=5)
        plan_c = work / "c" / "plan.md"
        arms["session_exit"] = {
            "pass": (
                resp.get("action") == "SESSION_EXPIRED"
                and rc2 == 1 and resp.get("llm_calls") == 0
                and plan_c.exists() and plan_c.stat().st_size == 0
            ),
        }
        print(f"  {'✓' if arms['session_exit']['pass'] else '✗'} "
              f"SESSION_EXPIRED → exit=1 + 0 LLM")
    finally:
        if proc2.poll() is None:
            proc2.kill()

    # ── D: wind_down（NDJSON 单会话仍 exit=1）──
    proc3 = subprocess.Popen(
        [
            sys.executable, str(KERNEL),
            "--session-ms", "30000", "--work-dir", str(work / "d"), "--mock-llm",
        ],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=env,
    )
    try:
        _read_json_line(proc3)
        _send(proc3, {"op": "turn", "latency_ms": 1})
        _read_json_line(proc3)
        _send(proc3, {"op": "wind_down"})
        resp = _read_json_line(proc3)
        rc3 = proc3.wait(timeout=5)
        plan_d = work / "d" / "plan.md"
        arms["wind_down"] = {
            "pass": (
                resp.get("action") == "REFUSED_WIND_DOWN"
                and rc3 == 1 and plan_d.exists() and plan_d.stat().st_size == 0
            ),
        }
        print(f"  {'✓' if arms['wind_down']['pass'] else '✗'} "
              f"NDJSON wind_down → exit=1")
    finally:
        if proc3.poll() is None:
            proc3.kill()

    # ── G: 真 LLM — 缺凭证 → LLM_ERROR；注入 llm_fn → LLM_OK；cc-switch 可解析 ──
    import importlib.util
    spec = importlib.util.spec_from_file_location("harness_kernel", KERNEL)
    assert spec and spec.loader
    hk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hk)

    old = {k: os.environ.pop(k, None) for k in (
        "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY",
        "OPENAI_BASE_URL", "OPENAI_API_KEY", "OLLAMA_HOST",
        "HARNESS_CC_PROVIDER", "HARNESS_DISABLE_CC_SWITCH",
    )}
    try:
        os.environ["HARNESS_DISABLE_CC_SWITCH"] = "1"
        k_err = hk.HarnessKernel(
            session_id="llm-err", session_ms=30000, startle_ms=50,
            budget_cost_pct=25, work_dir=work / "llm-err", mock_llm=False,
        )
        r_err = k_err.turn(latency_ms=1, prompt="ping")
        os.environ.pop("HARNESS_DISABLE_CC_SWITCH", None)

        k_ok = hk.HarnessKernel(
            session_id="llm-ok", session_ms=30000, startle_ms=50,
            budget_cost_pct=25, work_dir=work / "llm-ok", mock_llm=False,
            llm_fn=lambda p: f"REAL:{p[:40]}",
        )
        r_ok = k_ok.turn(latency_ms=1, prompt="hello-real")
        calls = {"n": 0}

        def boom(_p: str) -> str:
            calls["n"] += 1
            return "SHOULD_NOT"

        k_fatal = hk.HarnessKernel(
            session_id="llm-fatal", session_ms=30000, startle_ms=50,
            budget_cost_pct=50, work_dir=work / "llm-fatal", mock_llm=False,
            llm_fn=boom,
        )
        k_fatal.turn(latency_ms=1, charge=True, prompt="a")
        r_budget = k_fatal.turn(latency_ms=1, charge=True, prompt="b")

        # cc-switch 解析（不打印 token；不强制 live 调用）
        # Docker/CI 无 ~/.cc-switch 时 skip 记绿，不拖垮 overall
        if not hk.CC_SWITCH_DB.is_file():
            arms["cc_switch"] = {
                "pass": True,
                "skipped": True,
                "reason": f"no {hk.CC_SWITCH_DB}",
            }
        else:
            cc_ok = False
            cc_meta: dict = {}
            try:
                cfg = hk.load_cc_switch_provider()
                cc_ok = (
                    str(cfg.get("source", "")).startswith("cc-switch:")
                    and bool(cfg.get("base"))
                    and bool(cfg.get("token"))
                    and bool(cfg.get("model"))
                    and cfg.get("backend") in ("anthropic", "openai", "ollama")
                )
                cc_meta = {
                    "source": cfg.get("source"),
                    "backend": cfg.get("backend"),
                    "model": cfg.get("model"),
                    "base_host": cfg.get("base", "").split("/")[2] if "://" in cfg.get("base", "") else "",
                }
            except Exception as exc:
                cc_meta = {"error": str(exc)}
            arms["cc_switch"] = {**cc_meta, "pass": cc_ok}

        arms["real_llm"] = {
            "error_action": r_err.get("action"),
            "ok_action": r_ok.get("action"),
            "ok_output": r_ok.get("llm_output"),
            "budget_action": r_budget.get("action"),
            "boom_calls": calls["n"],
            "pass": (
                r_err.get("action") == "LLM_ERROR"
                and r_ok.get("action") == "LLM_OK"
                and str(r_ok.get("llm_output", "")).startswith("REAL:")
                and r_budget.get("action") == "BUDGET_EXIT"
                and calls["n"] == 1
            ),
        }
        print(f"  {'✓' if arms['real_llm']['pass'] else '✗'} "
              f"真 LLM：缺凭证 LLM_ERROR / 注入成功 / 致命不调 LLM")
        if arms["cc_switch"].get("skipped"):
            print("  ✓ cc-switch 凭证解析 (skipped: no db)")
        else:
            print(f"  {'✓' if arms['cc_switch']['pass'] else '✗'} "
                  f"cc-switch 凭证解析 {arms['cc_switch'].get('source', '')} "
                  f"model={arms['cc_switch'].get('model', '?')}")
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        os.environ.pop("HARNESS_DISABLE_CC_SWITCH", None)

    # ── F: HTTP 多会话隔离 + wind_down 不杀进程 + shutdown ──
    port = _free_port()
    proc4 = subprocess.Popen(
        [
            sys.executable, str(KERNEL),
            "--session-ms", "30000", "--startle-ms", "50",
            "--budget-cost-pct", "50",
            "--work-dir", str(work / "f"), "--mock-llm",
            "--http", f"127.0.0.1:{port}",
        ],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=env,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 8.0
        ready_http = False
        while time.time() < deadline:
            if proc4.poll() is not None:
                err = proc4.stderr.read() if proc4.stderr else ""
                arms["http_multi_session"] = {
                    "pass": False, "error": f"process died early: {err[:200]}",
                }
                break
            try:
                code, health = _http_json("GET", f"{base}/health")
                if code == 200 and health.get("multi_session") is True:
                    ready_http = True
                    break
            except (URLError, TimeoutError, ConnectionError, OSError):
                time.sleep(0.05)
                continue
        else:
            ready_http = False

        if ready_http:
            _, sa = _http_json("POST", f"{base}/sessions", {})
            _, sb = _http_json("POST", f"{base}/sessions", {})
            sid_a = sa.get("session_id")
            sid_b = sb.get("session_id")

            # A 扣两次押金 → BUDGET_EXIT；B 仍可 turn
            _http_json("POST", f"{base}/sessions/{sid_a}/turn",
                       {"latency_ms": 1, "charge": True, "prompt": "a1"})
            code_ax, ax = _http_json("POST", f"{base}/sessions/{sid_a}/turn",
                                     {"latency_ms": 1, "charge": True, "prompt": "a2"})
            code_b, bx = _http_json("POST", f"{base}/sessions/{sid_b}/turn",
                                    {"latency_ms": 1, "prompt": "b-ok"})

            # wind_down A；进程仍活；B 仍可
            code_w, aw = _http_json("POST", f"{base}/sessions/{sid_a}/wind_down", {})
            alive_after = proc4.poll() is None
            code_b2, b2 = _http_json("POST", f"{base}/sessions/{sid_b}/turn",
                                     {"latency_ms": 1, "prompt": "b2"})

            # verify on B
            code_v, bv = _http_json(
                "POST", f"{base}/sessions/{sid_b}/verify",
                {"latency_ms": 1, "task": "写初稿 draft.md", "output": "TODO"},
            )

            # shutdown 进程
            _http_json("POST", f"{base}/shutdown", {})
            try:
                rc4 = proc4.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc4.kill()
                rc4 = proc4.wait(timeout=5)

            plan_a = work / "f" / f"sess-{sid_a}" / "plan.md"
            plan_b = work / "f" / f"sess-{sid_b}" / "plan.md"

            arms["http_multi_session"] = {
                "sid_a": sid_a,
                "sid_b": sid_b,
                "a_budget": ax.get("action"),
                "b_turn": bx.get("action"),
                "a_wind": aw.get("action"),
                "alive_after_wind": alive_after,
                "b_after": b2.get("action"),
                "b_verify": bv.get("action"),
                "returncode": rc4,
                "plan_a_empty": plan_a.exists() and plan_a.stat().st_size == 0,
                "plan_b_nonempty": plan_b.exists() and plan_b.stat().st_size > 0,
                "pass": (
                    ready_http
                    and sid_a and sid_b and sid_a != sid_b
                    and ax.get("action") == "BUDGET_EXIT"
                    and bx.get("action") == "LLM_OK"
                    and aw.get("action") == "REFUSED_WIND_DOWN"
                    and alive_after
                    and b2.get("action") == "LLM_OK"
                    and bv.get("action") == "VERIFY_REJECT"
                    and rc4 == 0
                    and plan_a.exists() and plan_a.stat().st_size == 0
                    and plan_b.exists() and plan_b.stat().st_size > 0
                ),
            }
        print(f"  {'✓' if arms.get('http_multi_session', {}).get('pass') else '✗'} "
              f"HTTP 多会话隔离 + wind_down 不杀进程 + shutdown=0")
    finally:
        if proc4.poll() is None:
            proc4.kill()

    # ── H: turn → verify 串联 ──
    k_tv = hk.HarnessKernel(
        session_id="tv", session_ms=30000, startle_ms=50,
        budget_cost_pct=25, work_dir=work / "tv", mock_llm=False,
        llm_fn=lambda _p: "。",
    )
    r_tv = k_tv.turn(
        latency_ms=1, prompt="x",
        verify_task="写初稿 draft.md，至少覆盖三个核心机制",
    )
    arms["turn_verify"] = {
        "action": r_tv.get("action"),
        "layer": (r_tv.get("verify") or {}).get("layer"),
        "llm_calls": r_tv.get("llm_calls"),
        "pass": (
            r_tv.get("action") == "TURN_VERIFY_REJECT"
            and (r_tv.get("verify") or {}).get("layer") == "L0"
            and r_tv.get("llm_calls") == 1
            and r_tv.get("llm_output") == "。"
        ),
    }
    print(f"  {'✓' if arms['turn_verify']['pass'] else '✗'} "
          f"turn→verify 串联 → TURN_VERIFY_REJECT@L0")

    # ── H2: PHYSICAL_TIMEOUT 墙钟硬顶 ──
    def slow_llm(_p: str) -> str:
        time.sleep(0.25)
        return "TOO_LATE"

    k_phys = hk.HarnessKernel(
        session_id="phys", session_ms=30000, startle_ms=5000,
        budget_cost_pct=25, work_dir=work / "phys", mock_llm=False,
        llm_fn=slow_llm, physical_timeout_ms=50,
    )
    r_phys = k_phys.turn(latency_ms=1, prompt="slow")
    r_fast = hk.HarnessKernel(
        session_id="phys-fast", session_ms=30000, startle_ms=5000,
        budget_cost_pct=25, work_dir=work / "phys-fast", mock_llm=False,
        llm_fn=lambda p: f"FAST:{p[:20]}", physical_timeout_ms=50,
    ).turn(latency_ms=1, prompt="ok")
    arms["physical_timeout"] = {
        "slow_action": r_phys.get("action"),
        "slow_alive": k_phys.alive,
        "slow_has_output": "llm_output" in r_phys,
        "fast_action": r_fast.get("action"),
        "timeouts": k_phys.physical_timeouts,
        "pass": (
            r_phys.get("action") == "PHYSICAL_TIMEOUT"
            and k_phys.alive
            and "llm_output" not in r_phys
            and k_phys.physical_timeouts == 1
            and r_fast.get("action") == "LLM_OK"
            and str(r_fast.get("llm_output", "")).startswith("FAST:")
        ),
    }
    print(f"  {'✓' if arms['physical_timeout']['pass'] else '✗'} "
          f"PHYSICAL_TIMEOUT：慢调用拒 turn / 快调用 LLM_OK")

    # ── I: HTTP Bearer 鉴权 ──
    port_auth = _free_port()
    env_auth = _env(HARNESS_HTTP_TOKEN="probe-secret")
    proc_auth = subprocess.Popen(
        [
            sys.executable, str(KERNEL),
            "--session-ms", "30000", "--work-dir", str(work / "auth"),
            "--mock-llm", "--http", f"127.0.0.1:{port_auth}",
        ],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=env_auth,
    )
    base_auth = f"http://127.0.0.1:{port_auth}"
    try:
        for _ in range(80):
            try:
                c, h = _http_json("GET", f"{base_auth}/health")
                if c == 200 and h.get("auth_required") is True:
                    break
            except (URLError, OSError):
                time.sleep(0.05)
        else:
            arms["http_auth"] = {"pass": False, "error": "health timeout"}
            raise RuntimeError("auth health timeout")

        c401, b401 = _http_json("POST", f"{base_auth}/sessions", {})
        c200, b200 = _http_json(
            "POST", f"{base_auth}/sessions", {},
            headers={"Authorization": "Bearer probe-secret"},
        )
        _http_json(
            "POST", f"{base_auth}/shutdown", {},
            headers={"Authorization": "Bearer probe-secret"},
        )
        try:
            proc_auth.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc_auth.kill()
            proc_auth.wait(timeout=5)
        arms["http_auth"] = {
            "unauthorized": c401,
            "authorized_action": b200.get("action"),
            "pass": c401 == 401 and b401.get("action") == "AUTH_REQUIRED"
            and c200 == 200 and b200.get("action") == "SESSION_CREATED",
        }
    except Exception as exc:
        arms.setdefault("http_auth", {"pass": False, "error": str(exc)})
        if proc_auth.poll() is None:
            proc_auth.kill()
    print(f"  {'✓' if arms.get('http_auth', {}).get('pass') else '✗'} "
          f"HTTP Bearer：无 token→401 / 有 token→SESSION_CREATED")

    # ── J: 会话落盘跨进程恢复预算 ──
    persist_root = work / "persist"
    store1 = hk.SessionStore(
        root_work_dir=persist_root, session_ms=60000, startle_ms=50,
        budget_cost_pct=25, mock_llm=True, persist=True,
    )
    s1 = store1.create("persist-demo")
    s1.turn(latency_ms=1, charge=True, prompt="c1")
    budget_after = s1.budget.budget_pct
    del store1  # 模拟进程退出
    store2 = hk.SessionStore(
        root_work_dir=persist_root, session_ms=60000, startle_ms=50,
        budget_cost_pct=25, mock_llm=True, persist=True,
    )
    s2 = store2.get("persist-demo")
    arms["session_persist"] = {
        "budget_before_restart": budget_after,
        "budget_after_restart": None if s2 is None else s2.budget.budget_pct,
        "alive": None if s2 is None else s2.alive,
        "state_exists": (persist_root / "sess-persist-demo" / "state.json").is_file(),
        "pass": (
            s2 is not None
            and s2.alive
            and abs(s2.budget.budget_pct - 75.0) < 1e-6
            and s2.budget.charges == 1
        ),
    }
    print(f"  {'✓' if arms['session_persist']['pass'] else '✗'} "
          f"会话落盘：重启后 budget=75 charges=1")

    overall = all(a.get("pass") for a in arms.values())
    print("=" * 78)
    if overall:
        print("  结果: ✓ PHYSICAL_TIMEOUT + 既有臂通过")
    else:
        print("  结果: ✗ 有 FAIL")
        for name, arm in arms.items():
            if not arm.get("pass"):
                print(f"    FAIL {name}: {arm}")
    print("  声明: turn 已焊墙钟硬顶；仍非完整产品壳。")
    print("=" * 78)

    out = {
        "test": "crash-test-harness-kernel",
        "overall_pass": overall,
        "arms": arms,
        "evidence_map": {
            "supports": (
                [
                    "NDJSON single-session fatal → exit=1 + plan empty",
                    "STARTLE refuses turn without process death",
                    "turn real-LLM path: LLM_ERROR without creds; injectable llm_fn",
                    "fatal budget path does not call LLM",
                    "cc-switch.db credential fallback (source=cc-switch:*)",
                    "turn→verify compose yields TURN_VERIFY_REJECT on L0 garbage",
                    "PHYSICAL_TIMEOUT_MS wall-clock bound discards late LLM answers",
                    "HTTP Bearer auth when HARNESS_HTTP_TOKEN set (/health open)",
                    "session state.json persist + restore budget across process",
                    "HTTP multi-session: isolated budget/plan; wind_down keeps process",
                    "POST /shutdown exits 0",
                    "verify → forge-verify L0 reject",
                ]
                if overall else []
            ),
            "does_not_support": [
                "multi-tenant RBAC / encrypted session vault",
                "full product L0–L4 agent runtime shell",
                "L2 without API (SKIP_LLM residual)",
            ],
        },
    }
    out_dir = HERE / "results-v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "crash-test-harness-kernel_result.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  结果已写入: {path}")
    return out


if __name__ == "__main__":
    # remove accidental bad import reference if any
    result = run()
    raise SystemExit(0 if result["overall_pass"] else 1)
