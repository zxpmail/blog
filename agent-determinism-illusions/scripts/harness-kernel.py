#!/usr/bin/env python3
"""
Harness Kernel — 可部署进程（组合桩的进程边界版）

Claim
-----
把 SessionLifetime + Startle + TokenBudget + plan 收尾 焊进常驻进程。
- NDJSON：默认单会话；致命路径清 plan 且 exit=1。
- HTTP：多会话（每会话独立守卫/plan）；单会话 wind_down 不杀进程；POST /shutdown 才退出。
- turn：HARNESS_MOCK_LLM=0 时走真 LLM（env ANTHROPIC_*，否则 ~/.cc-switch/cc-switch.db）；
  可选 `verify`/`verify_task` 串联 forge-verify；
  **PHYSICAL_TIMEOUT_MS 墙钟硬顶**（超时拒 turn、丢弃迟到答案，进程仍活）。
- HTTP：多会话 + state.json 落盘恢复；可选 HARNESS_HTTP_TOKEN Bearer 鉴权。
- verify：forge-verify layered_judge（SKIP_LLM 可只跑 L0/L1）。

仍不是完整产品运行时（无租户/RBAC、无加密会话仓、无 forge 全链路产品壳）。

Protocol (NDJSON)
-----------------
  → {"op":"turn","latency_ms":5,"charge":false,"prompt":"..."}
  → {"op":"verify","latency_ms":1,"task":"...","output":"..."}
  → {"op":"status"} | {"op":"wind_down"} | {"op":"shutdown"}

HTTP multi-session
------------------
  POST /sessions                         → 创建会话，返回 session_id
  GET  /sessions                         → 列表
  GET  /sessions/{id}/status
  POST /sessions/{id}/turn|verify|wind_down
  POST /turn|verify  + header X-Session-Id 或 body.session_id（缺则自动建）
  GET  /health
  POST /shutdown                         → 进程 exit 0

Env
---
  HARNESS_SESSION_MS / HARNESS_STARTLE_MS / HARNESS_BUDGET_COST_PCT
  HARNESS_WORK_DIR / HARNESS_MOCK_LLM / SKIP_LLM
  ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN|ANTHROPIC_API_KEY + ANTHROPIC_MODEL
  HARNESS_CC_PROVIDER / --provider   cc-switch provider 名（默认当前 is_current claude）
  HARNESS_DISABLE_CC_SWITCH=1        禁止回退 cc-switch（探针用）
  HARNESS_HTTP_TOKEN                 若设置，HTTP 需 Bearer 或 X-Harness-Token（/health 除外）
  HARNESS_PHYSICAL_TIMEOUT_MS        turn LLM 墙钟硬顶（默认 60000；探针可设 200）
  HARNESS_BASELINE_RTT_MS / HARNESS_L01_PROBE_MS  → 未设显式红线时 3×max 推导
  （URL 含 :11434 → Ollama；含 anthropic → Messages；否则 chat/completions）

Run
---
  python harness-kernel.py
  python harness-kernel.py --no-mock-llm --provider "Zhipu GLM copy"
  python harness-kernel.py --http 127.0.0.1:8765 --no-mock-llm

Falsify
-------
致命路径仍调了 LLM；多会话互相污染预算/plan；mock=0 无凭证却假装成功；
wind_down 单会话误杀 HTTP 进程；verify 未走 forge-verify；
有 cc-switch 却仍报未配置（除非 HARNESS_DISABLE_CC_SWITCH=1）。
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CC_SWITCH_DB = Path.home() / ".cc-switch" / "cc-switch.db"

# 模块级默认 provider（可由 --provider 写入）
_CC_PROVIDER_OVERRIDE: str | None = None


def derive_physical_timeout_ms() -> float:
    """
    与 crash-test-chaos 同形：优先显式红线；
    否则 3×max(BASELINE_RTT, L01_PROBE)；再否则默认 60000（LLM 实用值）。
    探针请显式设 HARNESS_PHYSICAL_TIMEOUT_MS=200 一类短红线。
    """
    raw = os.environ.get("HARNESS_PHYSICAL_TIMEOUT_MS", "").strip()
    if raw:
        return float(raw)
    baseline = float(os.environ.get("HARNESS_BASELINE_RTT_MS", "0") or 0)
    l01 = float(os.environ.get("HARNESS_L01_PROBE_MS", "0") or 0)
    if baseline > 0 or l01 > 0:
        return 3.0 * max(baseline, l01)
    return 60000.0


# ── LLM（env → cc-switch → 失败）────────────────────────────────

def _backend_for_base(base: str) -> str:
    if not base:
        return "none"
    if ":11434" in base or base.rstrip("/").endswith("11434"):
        return "ollama"
    if "anthropic" in base.lower():
        return "anthropic"
    return "openai"


def load_cc_switch_provider(provider_name: str | None = None) -> dict[str, str]:
    """
    从 ~/.cc-switch/cc-switch.db 读 Claude provider。
    顺序：显式名 → is_current=1 → 任意一个有凭证的 claude provider。
    不打印 token。
    """
    if os.environ.get("HARNESS_DISABLE_CC_SWITCH", "").strip() in ("1", "true", "yes"):
        raise RuntimeError("cc-switch disabled by HARNESS_DISABLE_CC_SWITCH=1")
    if not CC_SWITCH_DB.is_file():
        raise RuntimeError(f"cc-switch.db not found: {CC_SWITCH_DB}")

    name = (
        provider_name
        or _CC_PROVIDER_OVERRIDE
        or os.environ.get("HARNESS_CC_PROVIDER", "").strip()
        or None
    )
    con = sqlite3.connect(str(CC_SWITCH_DB))
    try:
        row = None
        if name:
            row = con.execute(
                "SELECT name, settings_config FROM providers "
                "WHERE app_type='claude' AND name=? COLLATE NOCASE",
                (name,),
            ).fetchone()
            if not row:
                raise RuntimeError(f"cc-switch provider not found: {name!r}")
        if row is None:
            row = con.execute(
                "SELECT name, settings_config FROM providers "
                "WHERE app_type='claude' AND is_current=1"
            ).fetchone()
        if row is None:
            row = con.execute(
                "SELECT name, settings_config FROM providers WHERE app_type='claude' LIMIT 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("cc-switch has no claude provider")
        pname, settings_raw = row
        env = json.loads(settings_raw or "{}").get("env") or {}
        base = (env.get("ANTHROPIC_BASE_URL") or "").strip()
        token = (
            env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY") or ""
        ).strip()
        model = (
            env.get("ANTHROPIC_MODEL")
            or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
            or ""
        ).strip()
        if not (base and token):
            raise RuntimeError(f"cc-switch provider {pname!r} missing base/token")
        if not model:
            model = "deepseek-v4-flash"
        return {
            "base": base,
            "token": token,
            "model": model,
            "backend": _backend_for_base(base),
            "source": f"cc-switch:{pname}",
        }
    finally:
        con.close()


def resolve_llm_config(provider_name: str | None = None) -> dict[str, str]:
    """优先 env；否则回退 cc-switch（与 stuck-loop / df-multiperspective 同形）。"""
    base = (
        os.environ.get("ANTHROPIC_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OLLAMA_HOST")
        or ""
    ).strip()
    token = (
        os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("VERIFY_API_KEY")
        or ""
    ).strip()
    model = (
        os.environ.get("ANTHROPIC_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or ""
    ).strip()

    if base and (token or _backend_for_base(base) == "ollama"):
        return {
            "base": base,
            "token": token,
            "model": model or "deepseek-v4-flash",
            "backend": _backend_for_base(base),
            "source": "env",
        }

    try:
        return load_cc_switch_provider(provider_name)
    except RuntimeError:
        if not base:
            return {
                "base": "",
                "token": "",
                "model": model or "deepseek-v4-flash",
                "backend": "none",
                "source": "none",
            }
        return {
            "base": base,
            "token": token,
            "model": model or "deepseek-v4-flash",
            "backend": _backend_for_base(base),
            "source": "env",
        }


def call_llm_text(prompt: str, *, max_tokens: int = 512, timeout_s: float = 60.0) -> str:
    """真 LLM 调用。缺配置或失败则抛 RuntimeError。"""
    cfg = resolve_llm_config()
    backend = cfg["backend"]
    if backend == "none" or not cfg["base"]:
        raise RuntimeError(
            "LLM 未配置：设 ANTHROPIC_* 或配置 ~/.cc-switch（可用 --provider）"
        )
    if backend != "ollama" and not cfg["token"]:
        raise RuntimeError("LLM 未配置：缺少 API token（env 或 cc-switch）")

    base = cfg["base"].rstrip("/")
    model = cfg["model"]

    if backend == "ollama":
        url = base + "/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        headers = {"Content-Type": "application/json"}
    elif backend == "anthropic":
        url = base + "/v1/messages"
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": cfg["token"],
            "anthropic-version": "2023-06-01",
        }
    else:
        url = base + "/chat/completions"
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['token']}",
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"LLM call failed: {exc}") from exc

    if backend == "ollama":
        return str((body.get("message") or {}).get("content") or "").strip()
    if backend == "anthropic":
        for block in body.get("content") or []:
            if block.get("type") == "text":
                return str(block.get("text") or "").strip()
        return ""
    choices = body.get("choices") or []
    if not choices:
        return ""
    return str((choices[0].get("message") or {}).get("content") or "").strip()


# ── 守卫 ───────────────────────────────────────────────────────────

class TokenBudgetDeposit:
    def __init__(self, initial_pct: float = 100.0, cost_pct: float = 25.0):
        self.initial_pct = float(initial_pct)
        self.budget_pct = float(initial_pct)
        self.cost_pct = float(cost_pct)
        self.exhausted = False
        self.charges = 0

    def charge(self) -> str:
        if self.exhausted:
            return "EXIT"
        self.budget_pct = max(0.0, self.budget_pct - self.cost_pct)
        self.charges += 1
        if self.budget_pct <= 0.0:
            self.exhausted = True
            return "EXIT"
        return "CONTINUE"


class StartleReflex:
    def __init__(self, threshold_ms: float):
        self.threshold_ms = float(threshold_ms)
        self.fired = False

    def observe(self, latency_ms: float) -> str:
        if latency_ms >= self.threshold_ms:
            self.fired = True
            return "STARTLE"
        return "OK"


class SessionLifetimeGuard:
    """墙钟截止；可跨进程恢复（expires_at）。"""

    def __init__(
        self,
        max_lifetime_ms: float,
        *,
        created_at: float | None = None,
        expires_at: float | None = None,
    ):
        self.max_lifetime_ms = float(max_lifetime_ms)
        self.created_at = float(created_at if created_at is not None else time.time())
        self.expires_at = float(
            expires_at
            if expires_at is not None
            else self.created_at + self.max_lifetime_ms / 1000.0
        )
        self.expired = False

    def elapsed_ms(self) -> float:
        return max(0.0, (time.time() - self.created_at) * 1000.0)

    def check(self) -> str:
        if time.time() >= self.expires_at:
            self.expired = True
            return "SESSION_EXPIRED"
        return "OK"


FATAL_ACTIONS = frozenset({"SESSION_EXPIRED", "BUDGET_EXIT", "REFUSED_WIND_DOWN"})

_VERIFY_ACTION = {
    "PASS": "VERIFY_PASS",
    "REJECT": "VERIFY_REJECT",
    "UNCLEAR": "VERIFY_UNCLEAR",
    "SKIP": "VERIFY_SKIP",
}


def _load_layered_judge() -> Callable[[str, str], dict]:
    path = HERE / "forge-verify-layered-prototype.py"
    spec = importlib.util.spec_from_file_location("forge_verify_layered", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.layered_judge


class HarnessKernel:
    """单会话内核：turn / verify 状态机 + plan 文件。"""

    def __init__(
        self,
        *,
        session_id: str,
        session_ms: float,
        startle_ms: float,
        budget_cost_pct: float,
        work_dir: Path,
        mock_llm: bool = True,
        llm_fn: Callable[[str], str] | None = None,
        persist: bool = False,
        physical_timeout_ms: float | None = None,
        created_at: float | None = None,
        expires_at: float | None = None,
    ):
        self.session_id = session_id
        self.session = SessionLifetimeGuard(
            max_lifetime_ms=session_ms,
            created_at=created_at,
            expires_at=expires_at,
        )
        self.startle = StartleReflex(threshold_ms=startle_ms)
        self.budget = TokenBudgetDeposit(initial_pct=100.0, cost_pct=budget_cost_pct)
        self.physical_timeout_ms = float(
            physical_timeout_ms if physical_timeout_ms is not None else derive_physical_timeout_ms()
        )
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.plan = self.work_dir / "plan.md"
        if not self.plan.exists():
            self.plan.write_text("# harness plan\n", encoding="utf-8")
        self.winding_down = False
        self.mock_llm = mock_llm
        self.llm_fn = llm_fn
        self.persist = persist
        self.llm_calls = 0
        self.verify_calls = 0
        self.turns = 0
        self.physical_timeouts = 0
        self.alive = True
        self._layered_judge: Callable[[str, str], dict] | None = None
        self._lock = threading.RLock()
        if self.persist:
            self.save_state()

    @property
    def state_path(self) -> Path:
        return self.work_dir / "state.json"

    def save_state(self) -> None:
        if not self.persist:
            return
        payload = {
            "session_id": self.session_id,
            "max_lifetime_ms": self.session.max_lifetime_ms,
            "created_at": self.session.created_at,
            "expires_at": self.session.expires_at,
            "startle_threshold_ms": self.startle.threshold_ms,
            "startle_fired": self.startle.fired,
            "budget_pct": self.budget.budget_pct,
            "budget_cost_pct": self.budget.cost_pct,
            "budget_charges": self.budget.charges,
            "budget_exhausted": self.budget.exhausted,
            "winding_down": self.winding_down,
            "alive": self.alive,
            "llm_calls": self.llm_calls,
            "verify_calls": self.verify_calls,
            "turns": self.turns,
            "mock_llm": self.mock_llm,
            "physical_timeout_ms": self.physical_timeout_ms,
            "physical_timeouts": self.physical_timeouts,
        }
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def from_state(
        cls,
        state_path: Path,
        *,
        mock_llm: bool,
        llm_fn: Callable[[str], str] | None = None,
        persist: bool = True,
    ) -> "HarnessKernel":
        data = json.loads(state_path.read_text(encoding="utf-8"))
        work = state_path.parent
        kernel = cls(
            session_id=str(data["session_id"]),
            session_ms=float(data["max_lifetime_ms"]),
            startle_ms=float(data["startle_threshold_ms"]),
            budget_cost_pct=float(data["budget_cost_pct"]),
            work_dir=work,
            mock_llm=mock_llm,
            llm_fn=llm_fn,
            persist=False,  # 避免构造时覆盖
            physical_timeout_ms=float(
                data.get("physical_timeout_ms", derive_physical_timeout_ms())
            ),
            created_at=float(data["created_at"]),
            expires_at=float(data["expires_at"]),
        )
        kernel.persist = persist
        kernel.startle.fired = bool(data.get("startle_fired", False))
        kernel.budget.budget_pct = float(data["budget_pct"])
        kernel.budget.charges = int(data.get("budget_charges", 0))
        kernel.budget.exhausted = bool(data.get("budget_exhausted", False))
        kernel.winding_down = bool(data.get("winding_down", False))
        kernel.alive = bool(data.get("alive", True))
        kernel.llm_calls = int(data.get("llm_calls", 0))
        kernel.verify_calls = int(data.get("verify_calls", 0))
        kernel.turns = int(data.get("turns", 0))
        kernel.physical_timeouts = int(data.get("physical_timeouts", 0))
        if persist:
            kernel.save_state()
        return kernel

    def _judge(self) -> Callable[[str, str], dict]:
        if self._layered_judge is None:
            self._layered_judge = _load_layered_judge()
        return self._layered_judge

    def _snapshot(self, action: str, **extra) -> dict:
        is_fatal = action in FATAL_ACTIONS
        return {
            "ok": not is_fatal and action != "LLM_ERROR",
            "action": action,
            "session_id": self.session_id,
            "llm_calls": self.llm_calls,
            "verify_calls": self.verify_calls,
            "turns": self.turns,
            "budget_pct": self.budget.budget_pct,
            "session_elapsed_ms": round(self.session.elapsed_ms(), 3),
            "session_max_ms": self.session.max_lifetime_ms,
            "session_expires_at": self.session.expires_at,
            "startle_threshold_ms": self.startle.threshold_ms,
            "physical_timeout_ms": self.physical_timeout_ms,
            "physical_timeouts": self.physical_timeouts,
            "winding_down": self.winding_down,
            "plan_empty": self.plan.exists() and self.plan.stat().st_size == 0,
            "alive": self.alive,
            "mock_llm": self.mock_llm,
            **extra,
        }

    def _call_llm(self, prompt: str) -> str:
        """同步调用（不计墙钟）。优先走 _invoke_llm_bounded。"""
        self.llm_calls += 1
        if self.mock_llm and self.llm_fn is None:
            return f"MOCK:{prompt[:80]}"
        if self.llm_fn is not None:
            return self.llm_fn(prompt)
        timeout_s = max(0.001, self.physical_timeout_ms / 1000.0)
        return call_llm_text(prompt, timeout_s=timeout_s)

    def _invoke_llm_bounded(self, prompt: str) -> tuple[str, float]:
        """
        墙钟硬顶 PHYSICAL_TIMEOUT_MS：超时抛 TimeoutError，丢弃迟到答案。
        返回 (text, elapsed_ms)。
        """
        timeout_s = max(0.001, self.physical_timeout_ms / 1000.0)
        box: dict[str, Any] = {}

        def worker() -> None:
            try:
                box["out"] = self._call_llm(prompt)
            except Exception as exc:  # noqa: BLE001 — 传回主线程
                box["err"] = exc

        thr = threading.Thread(target=worker, daemon=True)
        t0 = time.perf_counter()
        thr.start()
        thr.join(timeout_s)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if thr.is_alive():
            raise TimeoutError(
                f"PHYSICAL_TIMEOUT: wall {elapsed_ms:.1f}ms > "
                f"{self.physical_timeout_ms}ms"
            )
        if "err" in box:
            raise box["err"]
        return str(box.get("out", "")), elapsed_ms

    def clear_plan(self) -> None:
        self.plan.write_text("", encoding="utf-8")

    def _preflight(self, *, latency_ms: float, charge: bool) -> dict | None:
        if not self.alive:
            return self._snapshot("DEAD", ok=False)

        if self.winding_down:
            return self._snapshot("REFUSED_WIND_DOWN", ok=False)

        if self.session.check() == "SESSION_EXPIRED":
            self.clear_plan()
            self.alive = False
            self.save_state()
            return self._snapshot("SESSION_EXPIRED", ok=False)

        if self.startle.observe(latency_ms) == "STARTLE":
            self.save_state()
            return self._snapshot("STARTLE", ok=True, latency_ms=latency_ms)

        if charge:
            if self.budget.charge() == "EXIT":
                self.clear_plan()
                self.alive = False
                self.save_state()
                return self._snapshot("BUDGET_EXIT", ok=False)

        return None

    def _run_verify_on(self, output: str, task: str) -> tuple[str, dict]:
        self.verify_calls += 1
        result = self._judge()(output, task)
        verdict = str(result.get("final_verdict") or result.get("verdict") or "UNCLEAR")
        action = _VERIFY_ACTION.get(verdict, "VERIFY_UNCLEAR")
        slim = {
            "verdict": verdict,
            "layer": result.get("layer"),
            "L0": result.get("L0"),
            "L1": result.get("L1"),
            "L2": result.get("L2"),
        }
        return action, slim

    def turn(
        self,
        *,
        latency_ms: float,
        charge: bool = False,
        prompt: str = "",
        verify_task: str = "",
    ) -> dict:
        with self._lock:
            blocked = self._preflight(latency_ms=latency_ms, charge=charge)
            if blocked is not None:
                return blocked

            self.turns += 1
            try:
                out, wall_ms = self._invoke_llm_bounded(prompt or f"turn-{self.turns}")
            except TimeoutError as exc:
                self.physical_timeouts += 1
                self.save_state()
                return self._snapshot(
                    "PHYSICAL_TIMEOUT",
                    ok=True,
                    error=str(exc),
                    wall_ms=round(self.physical_timeout_ms, 3),
                )
            except Exception as exc:
                self.save_state()
                return self._snapshot("LLM_ERROR", ok=False, error=str(exc))

            if not verify_task:
                self.save_state()
                return self._snapshot(
                    "LLM_OK", ok=True, llm_output=out, wall_ms=round(wall_ms, 3)
                )

            v_action, slim = self._run_verify_on(out, verify_task)
            self.save_state()
            if slim["verdict"] == "REJECT":
                return self._snapshot(
                    "TURN_VERIFY_REJECT",
                    ok=True,
                    llm_output=out,
                    verify=slim,
                    wall_ms=round(wall_ms, 3),
                )
            return self._snapshot(
                "LLM_OK",
                ok=True,
                llm_output=out,
                verify=slim,
                verify_action=v_action,
                wall_ms=round(wall_ms, 3),
            )

    def verify(
        self,
        *,
        task: str,
        output: str,
        latency_ms: float = 0.0,
        charge: bool = False,
    ) -> dict:
        with self._lock:
            blocked = self._preflight(latency_ms=latency_ms, charge=charge)
            if blocked is not None:
                return blocked

            self.turns += 1
            action, slim = self._run_verify_on(output, task)
            self.save_state()
            return self._snapshot(action, ok=True, verify=slim)

    def wind_down(self) -> dict:
        with self._lock:
            self.winding_down = True
            self.clear_plan()
            self.alive = False
            self.save_state()
            return self._snapshot("REFUSED_WIND_DOWN", ok=False)

    def status(self) -> dict:
        with self._lock:
            return self._snapshot("STATUS", ok=True)

    def handle_request(self, req: dict) -> tuple[dict, bool]:
        """
        处理一条请求。
        返回 (response, session_fatal)。session_fatal 表示本会话已死（调用方勿再复用）。
        """
        op = req.get("op", "turn")
        if op == "status":
            return self.status(), not self.alive
        if op == "shutdown":
            self.clear_plan()
            self.save_state()
            return self._snapshot("SHUTDOWN", ok=True), True
        if op == "wind_down":
            return self.wind_down(), True
        if op == "verify":
            resp = self.verify(
                task=str(req.get("task", "")),
                output=str(req.get("output", "")),
                latency_ms=float(req.get("latency_ms", 0.0)),
                charge=bool(req.get("charge", False)),
            )
            return resp, resp["action"] in FATAL_ACTIONS
        if op != "turn":
            return {"ok": False, "action": "BAD_OP", "error": f"unknown op={op}",
                    "session_id": self.session_id}, False

        verify_task = ""
        if req.get("verify"):
            if isinstance(req.get("verify"), str):
                verify_task = str(req.get("verify"))
            else:
                verify_task = str(req.get("task", "") or req.get("verify_task", ""))
        elif req.get("verify_task"):
            verify_task = str(req.get("verify_task"))

        resp = self.turn(
            latency_ms=float(req.get("latency_ms", 0.0)),
            charge=bool(req.get("charge", False)),
            prompt=str(req.get("prompt", "")),
            verify_task=verify_task,
        )
        return resp, resp["action"] in FATAL_ACTIONS


class SessionStore:
    """HTTP 多会话：每会话独立 HarnessKernel（守卫 / plan / 预算隔离）。"""

    def __init__(
        self,
        *,
        root_work_dir: Path,
        session_ms: float,
        startle_ms: float,
        budget_cost_pct: float,
        mock_llm: bool,
        llm_fn: Callable[[str], str] | None = None,
        persist: bool = True,
        physical_timeout_ms: float | None = None,
    ):
        self.root_work_dir = root_work_dir
        self.root_work_dir.mkdir(parents=True, exist_ok=True)
        self.session_ms = session_ms
        self.startle_ms = startle_ms
        self.budget_cost_pct = budget_cost_pct
        self.mock_llm = mock_llm
        self.llm_fn = llm_fn
        self.persist = persist
        self.physical_timeout_ms = (
            float(physical_timeout_ms)
            if physical_timeout_ms is not None
            else derive_physical_timeout_ms()
        )
        self._sessions: dict[str, HarnessKernel] = {}
        self._lock = threading.RLock()
        if self.persist:
            self._restore_all()

    def _restore_all(self) -> None:
        for state_path in sorted(self.root_work_dir.glob("sess-*/state.json")):
            try:
                kernel = HarnessKernel.from_state(
                    state_path,
                    mock_llm=self.mock_llm,
                    llm_fn=self.llm_fn,
                    persist=True,
                )
                self._sessions[kernel.session_id] = kernel
            except Exception as exc:
                sys.stderr.write(f"skip restore {state_path}: {exc}\n")

    def create(self, session_id: str | None = None) -> HarnessKernel:
        with self._lock:
            sid = session_id or secrets.token_hex(8)
            if sid in self._sessions and self._sessions[sid].alive:
                raise ValueError(f"session already exists: {sid}")
            work = self.root_work_dir / f"sess-{sid}"
            kernel = HarnessKernel(
                session_id=sid,
                session_ms=self.session_ms,
                startle_ms=self.startle_ms,
                budget_cost_pct=self.budget_cost_pct,
                work_dir=work,
                mock_llm=self.mock_llm,
                llm_fn=self.llm_fn,
                persist=self.persist,
                physical_timeout_ms=self.physical_timeout_ms,
            )
            self._sessions[sid] = kernel
            return kernel

    def get(self, session_id: str) -> HarnessKernel | None:
        with self._lock:
            return self._sessions.get(session_id)

    def get_or_create(self, session_id: str | None) -> HarnessKernel:
        with self._lock:
            if session_id and session_id in self._sessions:
                k = self._sessions[session_id]
                if k.alive:
                    return k
            return self.create(session_id if session_id and session_id not in self._sessions else None)

    def list_sessions(self) -> list[dict]:
        with self._lock:
            out = []
            for sid, k in self._sessions.items():
                out.append({
                    "session_id": sid,
                    "alive": k.alive,
                    "budget_pct": k.budget.budget_pct,
                    "turns": k.turns,
                    "plan_empty": k.plan.exists() and k.plan.stat().st_size == 0,
                })
            return out

    def drop_if_dead(self, kernel: HarnessKernel) -> None:
        # 保留死会话记录便于 status；不强制删除
        return None


def _default_work_dir() -> Path:
    env = os.environ.get("HARNESS_WORK_DIR", "").strip()
    if env:
        return Path(env)
    ephemeral = os.environ.get("CRASH_TEST_EPHEMERAL_ROOT", "").strip()
    if ephemeral:
        return Path(ephemeral) / "harness-kernel-work"
    return HERE / "results-v2" / "_harness_work"


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _llm_ready_fields(*, mock_llm: bool) -> dict:
    if mock_llm:
        return {"llm_backend": "mock", "llm_source": "mock", "llm_model": None}
    cfg = resolve_llm_config()
    return {
        "llm_backend": cfg["backend"],
        "llm_source": cfg.get("source", "none"),
        "llm_model": cfg["model"] if cfg["backend"] != "none" else None,
    }


def serve_ndjson(kernel: HarnessKernel) -> int:
    """NDJSON 单会话：致命路径 → 进程 exit=1（保持探针语义）。"""
    _emit({
        "ok": True,
        "action": "READY",
        "transport": "ndjson",
        "session_id": kernel.session_id,
        "work_dir": str(kernel.work_dir),
        "session_max_ms": kernel.session.max_lifetime_ms,
        "startle_threshold_ms": kernel.startle.threshold_ms,
        "budget_cost_pct": kernel.budget.cost_pct,
        "mock_llm": kernel.mock_llm,
        "physical_timeout_ms": kernel.physical_timeout_ms,
        **_llm_ready_fields(mock_llm=kernel.mock_llm),
        "verify_enabled": True,
        "multi_session": False,
        "note": "ndjson single-session; fatal → exit 1; PHYSICAL_TIMEOUT refuses turn",
    })

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            _emit({"ok": False, "action": "BAD_JSON", "error": str(exc)})
            continue

        if req.get("op") == "shutdown":
            resp, _ = kernel.handle_request(req)
            _emit(resp)
            return 0

        resp, fatal = kernel.handle_request(req)
        _emit(resp)
        if fatal and resp.get("action") in FATAL_ACTIONS:
            return 1
        if fatal and resp.get("action") == "SHUTDOWN":
            return 0

    return 0 if kernel.alive else 1


_SESSION_PATH = re.compile(
    r"^/sessions/([^/]+)(?:/(turn|verify|wind_down|status))?$"
)


def _expected_http_token() -> str:
    return os.environ.get("HARNESS_HTTP_TOKEN", "").strip()


def _auth_ok(headers) -> bool:
    expected = _expected_http_token()
    if not expected:
        return True
    auth = headers.get("Authorization", "") or ""
    if auth.startswith("Bearer ") and auth[7:].strip() == expected:
        return True
    if (headers.get("X-Harness-Token") or "").strip() == expected:
        return True
    return False


def serve_http(store: SessionStore, host: str, port: int) -> int:
    """HTTP 多会话：单会话死亡不杀进程；POST /shutdown 才退出。可选 Bearer 鉴权。"""
    state: dict[str, Any] = {"exit_code": None}
    token_required = bool(_expected_http_token())

    def _http_code(resp: dict) -> int:
        action = resp.get("action")
        if action == "AUTH_REQUIRED":
            return 401
        if action in FATAL_ACTIONS:
            return 410
        if action == "LLM_ERROR":
            return 502
        if action == "DEAD":
            return 410
        if action == "BAD_OP":
            return 404
        if resp.get("ok", False) or action in (
            "STARTLE", "PHYSICAL_TIMEOUT",
            "VERIFY_PASS", "VERIFY_REJECT", "VERIFY_UNCLEAR", "VERIFY_SKIP",
            "TURN_VERIFY_REJECT", "STATUS", "READY", "SESSION_CREATED", "SESSION_LIST",
        ):
            return 200
        return 409

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def _write_json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if code == 401:
                self.send_header("WWW-Authenticate", 'Bearer realm="harness-kernel"')
            self.end_headers()
            self.wfile.write(body)

        def _require_auth(self) -> bool:
            if _auth_ok(self.headers):
                return True
            self._write_json(401, {
                "ok": False,
                "action": "AUTH_REQUIRED",
                "error": "missing or invalid Bearer / X-Harness-Token",
            })
            return False

        def _sid_from(self, body: dict | None = None) -> str | None:
            body = body or {}
            return (
                (body.get("session_id") if body else None)
                or self.headers.get("X-Session-Id")
                or None
            )

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in ("/health", "/ready"):
                # health 不加鉴权，便于探活；不泄露 token
                self._write_json(200, {
                    "ok": True,
                    "action": "READY",
                    "transport": "http",
                    "multi_session": True,
                    "persist": store.persist,
                    "auth_required": token_required,
                    "physical_timeout_ms": store.physical_timeout_ms,
                    "sessions": len(store.list_sessions()),
                    "mock_llm": store.mock_llm,
                    **_llm_ready_fields(mock_llm=store.mock_llm),
                    "verify_enabled": True,
                })
                return
            if not self._require_auth():
                return
            if path == "/sessions":
                self._write_json(200, {
                    "ok": True,
                    "action": "SESSION_LIST",
                    "sessions": store.list_sessions(),
                })
                return
            m = _SESSION_PATH.match(path)
            if m and (m.group(2) in (None, "status")):
                sid = m.group(1)
                kernel = store.get(sid)
                if kernel is None:
                    self._write_json(404, {"ok": False, "action": "BAD_OP",
                                           "error": f"unknown session {sid}"})
                    return
                self._write_json(200, kernel.status())
                return
            if path == "/status":
                self._write_json(200, {
                    "ok": True,
                    "action": "STATUS",
                    "sessions": store.list_sessions(),
                })
                return
            self._write_json(404, {"ok": False, "action": "BAD_OP", "error": path})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if not self._require_auth():
                return
            try:
                body = self._read_json()
            except json.JSONDecodeError as exc:
                self._write_json(400, {"ok": False, "action": "BAD_JSON", "error": str(exc)})
                return

            if path == "/sessions":
                want = body.get("session_id")
                try:
                    kernel = store.create(str(want) if want else None)
                except ValueError as exc:
                    self._write_json(409, {"ok": False, "action": "BAD_OP", "error": str(exc)})
                    return
                self._write_json(200, {
                    "ok": True,
                    "action": "SESSION_CREATED",
                    "session_id": kernel.session_id,
                    "work_dir": str(kernel.work_dir),
                    "persist": store.persist,
                })
                return

            if path == "/shutdown":
                self._write_json(200, {"ok": True, "action": "SHUTDOWN"})
                state["exit_code"] = 0
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return

            sid = None
            op = None
            m = _SESSION_PATH.match(path)
            if m and m.group(2) in ("turn", "verify", "wind_down"):
                sid = m.group(1)
                op = m.group(2)
            elif path in ("/turn", "/verify", "/wind_down"):
                op = path.lstrip("/")
                sid = self._sid_from(body)
            else:
                self._write_json(404, {"ok": False, "action": "BAD_OP", "error": path})
                return

            path_scoped = bool(m and m.group(2))
            if path_scoped:
                kernel = store.get(sid) if sid else None
                if kernel is None:
                    self._write_json(404, {"ok": False, "action": "BAD_OP",
                                           "error": f"unknown session {sid}"})
                    return
            else:
                kernel = store.get_or_create(sid)

            req = {"op": op, **{k: v for k, v in body.items() if k != "session_id"}}
            resp, _fatal = kernel.handle_request(req)
            self._write_json(_http_code(resp), resp)

    httpd = ThreadingHTTPServer((host, port), Handler)
    sys.stderr.write(
        json.dumps({
            "ok": True,
            "action": "READY",
            "transport": "http",
            "listen": f"{host}:{port}",
            "work_dir": str(store.root_work_dir),
            "mock_llm": store.mock_llm,
            **_llm_ready_fields(mock_llm=store.mock_llm),
            "multi_session": True,
            "persist": store.persist,
            "auth_required": token_required,
            "physical_timeout_ms": store.physical_timeout_ms,
            "verify_enabled": True,
            "note": "HTTP multi-session + persist/auth; PHYSICAL_TIMEOUT refuses turn",
        }, ensure_ascii=False)
        + "\n"
    )
    sys.stderr.flush()
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
    if state["exit_code"] is not None:
        return int(state["exit_code"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Harness Kernel (deployable process stub)")
    parser.add_argument(
        "--session-ms",
        type=float,
        default=float(os.environ.get("HARNESS_SESSION_MS", "60000")),
    )
    parser.add_argument(
        "--startle-ms",
        type=float,
        default=float(os.environ.get("HARNESS_STARTLE_MS", "50")),
    )
    parser.add_argument(
        "--budget-cost-pct",
        type=float,
        default=float(os.environ.get("HARNESS_BUDGET_COST_PCT", "25")),
    )
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument(
        "--mock-llm",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("HARNESS_MOCK_LLM", "1") not in ("0", "false", "no"),
    )
    parser.add_argument(
        "--http",
        default="",
        help="HTTP 多会话监听，如 127.0.0.1:8765；默认仅 NDJSON 单会话",
    )
    parser.add_argument(
        "--physical-timeout-ms",
        type=float,
        default=None,
        help="LLM 墙钟硬顶（默认 HARNESS_PHYSICAL_TIMEOUT_MS 或 60000）",
    )
    parser.add_argument(
        "--provider",
        default=os.environ.get("HARNESS_CC_PROVIDER", "").strip() or None,
        help="cc-switch Claude provider 名；默认用 is_current",
    )
    args = parser.parse_args(argv)

    global _CC_PROVIDER_OVERRIDE
    _CC_PROVIDER_OVERRIDE = args.provider

    work = args.work_dir or _default_work_dir()
    phys = (
        args.physical_timeout_ms
        if args.physical_timeout_ms is not None
        else derive_physical_timeout_ms()
    )

    if args.http:
        host, _, port_s = args.http.partition(":")
        if not host or not port_s:
            raise SystemExit("--http 需要 HOST:PORT，例如 127.0.0.1:8765")
        store = SessionStore(
            root_work_dir=work,
            session_ms=args.session_ms,
            startle_ms=args.startle_ms,
            budget_cost_pct=args.budget_cost_pct,
            mock_llm=args.mock_llm,
            physical_timeout_ms=phys,
        )
        return serve_http(store, host, int(port_s))

    kernel = HarnessKernel(
        session_id="default",
        session_ms=args.session_ms,
        startle_ms=args.startle_ms,
        budget_cost_pct=args.budget_cost_pct,
        work_dir=work,
        mock_llm=args.mock_llm,
        physical_timeout_ms=phys,
    )
    return serve_ndjson(kernel)


if __name__ == "__main__":
    if hasattr(sys.stdout, "buffer"):
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
        except Exception:
            pass
    if hasattr(sys.stdin, "buffer"):
        try:
            sys.stdin = io.TextIOWrapper(
                sys.stdin.buffer, encoding="utf-8", errors="replace"
            )
        except Exception:
            pass
    raise SystemExit(main())
