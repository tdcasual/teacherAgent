#!/usr/bin/env python3
"""
Student chat concurrency smoke test (local).

What it does:
- Starts a local stub OpenAI-compatible chat endpoint (so we don't hit real providers).
- Starts the FastAPI server via uvicorn on a random port (configurable workers).
- Fires concurrent /chat requests and reports basic latency stats.

This is intentionally light-weight (requests + threads) to keep dependencies minimal.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


ROOT = Path(__file__).resolve().parents[1]


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _LLMStubHandler(BaseHTTPRequestHandler):
    # configurable failure injection
    fail_first: int = 0
    seen: int = 0
    delay_ms: int = 0

    def log_message(self, format, *args):  # noqa: A002
        return

    def do_POST(self):  # noqa: N802
        _LLMStubHandler.seen += 1
        if _LLMStubHandler.delay_ms:
            time.sleep(_LLMStubHandler.delay_ms / 1000.0)
        if _LLMStubHandler.fail_first and _LLMStubHandler.seen <= _LLMStubHandler.fail_first:
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"rate_limited"}')
            return

        # Mimic OpenAI chat completions response shape.
        payload = {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 1}}
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _write_registry(path: Path, llm_port: int) -> None:
    content = f"""
defaults:
  provider: openai
  mode: openai-chat
  timeout_sec: 10
  retry: 2
providers:
  openai:
    api_key_envs: [LLM_API_KEY]
    auth:
      type: bearer
      header: Authorization
      prefix: "Bearer "
    modes:
      openai-chat:
        endpoint: /v1/chat/completions
        base_url: http://127.0.0.1:{llm_port}
        default_model: test-model
"""
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _wait_health(base_url: str, timeout_sec: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_sec
    last_err = None
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{base_url}/health", timeout=1.5)
            if r.status_code == 200:
                return
            last_err = RuntimeError(f"health status {r.status_code}")
        except Exception as exc:
            last_err = exc
        time.sleep(0.15)
    raise RuntimeError(f"server health not ready: {last_err}")


def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = int(round((len(sorted_vals) - 1) * p))
    idx = max(0, min(len(sorted_vals) - 1, idx))
    return sorted_vals[idx]


def _post_chat(base_url: str, payload: Dict[str, Any], timeout: float) -> Tuple[bool, float, str]:
    t0 = time.monotonic()
    try:
        r = requests.post(f"{base_url}/chat", json=payload, timeout=timeout)
        dt = time.monotonic() - t0
        if r.status_code != 200:
            return False, dt, f"http_{r.status_code}:{r.text[:120]}"
        data = r.json()
        reply = (data.get("reply") or "").strip()
        if not reply:
            return False, dt, "empty_reply"
        return True, dt, ""
    except Exception as exc:
        dt = time.monotonic() - t0
        return False, dt, f"exc:{type(exc).__name__}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Student /chat concurrency smoke test (local stub LLM)")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--requests", type=int, default=40, help="total request count")
    parser.add_argument("--workers", type=int, default=2, help="uvicorn workers")
    parser.add_argument("--timeout", type=float, default=30.0, help="per-request timeout")
    parser.add_argument("--fail-first-llm", type=int, default=0, help="LLM stub: fail first N with 429")
    parser.add_argument("--llm-delay-ms", type=int, default=0, help="LLM stub: per-request delay (ms)")
    parser.add_argument("--role", default="student", choices=["student", "teacher"])
    parser.add_argument("--with-student-id", action="store_true", help="include student_id in requests")
    parser.add_argument(
        "--profile-update",
        default="off",
        choices=["off", "async", "sync"],
        help="profile update mode (only relevant when role=student and --with-student-id)",
    )
    args = parser.parse_args()

    # 1) Start local LLM stub.
    llm_port = _find_free_port()
    _LLMStubHandler.fail_first = max(0, int(args.fail_first_llm))
    _LLMStubHandler.delay_ms = max(0, int(args.llm_delay_ms))
    llm_server = ThreadingHTTPServer(("127.0.0.1", llm_port), _LLMStubHandler)
    llm_thread = threading.Thread(target=llm_server.serve_forever, daemon=True)
    llm_thread.start()

    # 2) Write a temporary registry pointing to the stub.
    tmp_dir = ROOT / "tmp" / "smoke_student_chat"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    registry_path = tmp_dir / "model_registry.yaml"
    _write_registry(registry_path, llm_port)

    # 3) Start API server.
    api_port = _find_free_port()
    base_url = f"http://127.0.0.1:{api_port}"
    env = os.environ.copy()
    env["MODEL_REGISTRY_PATH"] = str(registry_path)
    env.setdefault("LLM_API_KEY", "local")
    env["LLM_PROVIDER"] = "openai"
    env["LLM_MODE"] = "openai-chat"
    # Ensure retries can cover our failure injection.
    env["LLM_RETRY"] = env.get("LLM_RETRY", "4")
    env["LLM_MAX_CONCURRENCY_STUDENT"] = env.get("LLM_MAX_CONCURRENCY_STUDENT", "12")
    env["LLM_MAX_CONCURRENCY_TEACHER"] = env.get("LLM_MAX_CONCURRENCY_TEACHER", "2")
    if args.profile_update == "off":
        # keep smoke test focused on /chat throughput
        env["PROFILE_UPDATE_ASYNC"] = "1"  # enabled, but no-op unless student_id present
    elif args.profile_update == "async":
        env["PROFILE_UPDATE_ASYNC"] = "1"
    else:
        env["PROFILE_UPDATE_ASYNC"] = "0"
    env["PROFILE_CACHE_TTL_SEC"] = env.get("PROFILE_CACHE_TTL_SEC", "10")
    env["ASSIGNMENT_DETAIL_CACHE_TTL_SEC"] = env.get("ASSIGNMENT_DETAIL_CACHE_TTL_SEC", "10")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "services.api.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(api_port),
        "--workers",
        str(int(args.workers)),
    ]
    api_proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        _wait_health(base_url, timeout_sec=12.0)

        # 4) Fire concurrent /chat requests.
        total = int(args.requests)
        conc = max(1, int(args.concurrency))
        role = args.role

        def build_payload(i: int) -> Dict[str, Any]:
            sid = f"s_{i}_{random.randint(1, 999999)}" if args.with_student_id else None
            payload = {
                "role": role,
                "messages": [{"role": "user", "content": f"ping {i}"}],
            }
            if sid:
                payload["student_id"] = sid
            return payload

        latencies: List[float] = []
        errors: Dict[str, int] = {}
        ok = 0
        t_all = time.monotonic()
        with ThreadPoolExecutor(max_workers=conc) as ex:
            futs = [ex.submit(_post_chat, base_url, build_payload(i), float(args.timeout)) for i in range(total)]
            for fut in as_completed(futs):
                success, dt, err = fut.result()
                latencies.append(dt)
                if success:
                    ok += 1
                else:
                    errors[err] = errors.get(err, 0) + 1
        dt_all = time.monotonic() - t_all

        lat_sorted = sorted(latencies)
        p50 = _percentile(lat_sorted, 0.50)
        p95 = _percentile(lat_sorted, 0.95)
        p99 = _percentile(lat_sorted, 0.99)
        avg = sum(lat_sorted) / len(lat_sorted) if lat_sorted else 0.0
        rps = ok / dt_all if dt_all > 0 else 0.0

        print("[RESULT]")
        print(f"workers={args.workers} concurrency={conc} total={total} ok={ok} seconds={dt_all:.3f} rps={rps:.2f}")
        print(f"latency_sec: p50={p50:.3f} p95={p95:.3f} p99={p99:.3f} avg={avg:.3f}")
        if errors:
            top = sorted(errors.items(), key=lambda x: x[1], reverse=True)[:8]
            print("errors:")
            for k, v in top:
                print(f"- {k}: {v}")
    finally:
        try:
            api_proc.terminate()
            api_proc.wait(timeout=4)
        except Exception:
            try:
                api_proc.kill()
            except Exception:
                pass
        try:
            llm_server.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
