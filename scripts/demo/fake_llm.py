#!/usr/bin/env python3
"""Fake, keyless LLM for the TeDDy showcase spike.

Serves an OpenAI-compatible chat-completions endpoint that LiteLLM calls
when TeDDy's llm.model is "openai/<name>" and llm.api_base points here.
Each planning request returns the next canned plan from plans/turn*.md,
cycling in order, so a multi-turn session is deterministic and offline.
"""

import json
import os
import random
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PLANS_DIR = Path(__file__).resolve().parent / "plans"
STATE_FILE = Path(os.environ.get("FAKE_LLM_STATE", "/tmp/teddy_fake_llm_state"))
LOG_FILE = Path(os.environ.get("FAKE_LLM_LOG", "/tmp/teddy_fake_llm.log"))


def _log(line):
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def _next_plan():
    plans = sorted(PLANS_DIR.glob("turn*.md"))
    if not plans:
        return "# Empty Plan\n\n## Message\n\nNo canned plan available.\n"
    index = 0
    if STATE_FILE.exists():
        try:
            index = int(STATE_FILE.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            index = 0
    plan = plans[index % len(plans)]
    STATE_FILE.write_text(str(index + 1), encoding="utf-8")
    _log("serving " + plan.name + " (index " + str(index) + ")")
    return plan.read_text(encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._json(
                200,
                {"object": "list", "data": [{"id": "fake-model", "object": "model"}]},
            )
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            request = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            request = {}
        _log("POST " + self.path + " stream=" + str(request.get("stream")))
        delay_min = float(os.environ.get("FAKE_LLM_DELAY_MIN", "3.0"))
        delay_max = float(os.environ.get("FAKE_LLM_DELAY_MAX", "5.0"))
        time.sleep(random.uniform(delay_min, delay_max))
        content = _next_plan()
        model_name = os.environ.get("FAKE_LLM_MODEL", "deepseek/deepseek-v4.1-flash")
        if request.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            chunk = {
                "id": "fake-1",
                "object": "chat.completion.chunk",
                "model": model_name,
                "choices": [
                    {"index": 0, "delta": {"role": "assistant", "content": content}}
                ],
            }
            self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            self._json(
                200,
                {
                    "id": "fake-1",
                    "object": "chat.completion",
                    "created": 0,
                    "model": model_name,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 7100,
                        "completion_tokens": 420,
                        "total_tokens": 7520,
                    },
                },
            )


def main():
    port = int(os.environ.get("FAKE_LLM_PORT", "8123"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("fake LLM listening on http://127.0.0.1:" + str(port), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
