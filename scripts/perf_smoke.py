#!/usr/bin/env python3
"""
Quick, dependency-free performance smoke test.

This script starts a tiny local HTTP server that mimics an OpenAI-compatible
chat endpoint, then runs a batch of LLMGateway requests against it. It helps
verify:
- registry loading works
- requests.Session keep-alive path doesn't crash
- retry/backoff path works (optional failure injection)

It does NOT test real provider latency.
"""

import argparse
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import sys

# Ensure project root is importable when executed as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llm_gateway import LLMGateway, UnifiedLLMRequest


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Handler(BaseHTTPRequestHandler):
    # Shared state (simple): fail first N requests with 429
    fail_first = 0
    seen = 0

    def log_message(self, format, *args):  # noqa: A002
        return

    def do_POST(self):  # noqa: N802
        Handler.seen += 1
        if Handler.fail_first and Handler.seen <= Handler.fail_first:
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"rate_limited"}')
            return

        body = {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 1}}
        raw = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def write_temp_registry(path: Path, port: int) -> None:
    # Minimal registry that points openai-chat to our local server.
    content = f"""
defaults:
  provider: openai
  mode: openai-chat
  timeout_sec: 10
  retry: 4
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
        base_url: http://127.0.0.1:{port}
        default_model: test-model
"""
    path.write_text(content.strip() + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="LLM gateway performance smoke test (local stub)")
    parser.add_argument("--n", type=int, default=50, help="number of requests")
    parser.add_argument("--fail-first", type=int, default=0, help="fail first N requests with HTTP 429")
    args = parser.parse_args()

    port = find_free_port()
    Handler.fail_first = max(0, int(args.fail_first))
    server = HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    tmp_dir = Path("tmp") / "perf_smoke"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    registry_path = tmp_dir / "registry.yaml"
    write_temp_registry(registry_path, port)

    # Required by registry api_key_envs; stub server ignores it.
    import os

    os.environ.setdefault("LLM_API_KEY", "local")
    os.environ["MODEL_REGISTRY_PATH"] = str(registry_path)

    gateway = LLMGateway()
    req = UnifiedLLMRequest(messages=[{"role": "user", "content": "ping"}], temperature=0)

    t0 = time.monotonic()
    ok = 0
    for _ in range(int(args.n)):
        resp = gateway.generate(req, allow_fallback=False)
        if resp.text.strip() == "ok":
            ok += 1
    dt = time.monotonic() - t0

    server.shutdown()

    rps = ok / dt if dt > 0 else 0.0
    print(f"[OK] requests={args.n} ok={ok} seconds={dt:.3f} rps={rps:.1f} fail_first={args.fail_first}")


if __name__ == "__main__":
    main()
