"""Reproduce `teddy start` with piped (non-TTY) stdin in a throwaway project.

Two cases isolate the preflight: without an LLM API key the run must stop at
configuration validation, with a key it reaches the opening prompt. The
elapsed time proves whether either case waits for terminal input.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TIMEOUT_SECONDS = 60


def run_start_case(label: str, api_key: str | None) -> dict:
    with tempfile.TemporaryDirectory(prefix="teddy-nontty-") as project_dir:
        env = {
            key: value
            for key, value in os.environ.items()
            if key != "TEDDY_LLM_API_KEY"
        }
        env["NO_COLOR"] = "1"
        if api_key is not None:
            env["TEDDY_LLM_API_KEY"] = api_key
        started = time.monotonic()
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "teddy_executor", "start"],
                cwd=project_dir,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as error:
            return {
                "case": label,
                "timed_out": True,
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "stdout_tail": (error.stdout or "")[-800:],
                "stderr_tail": (error.stderr or "")[-800:],
            }
        elapsed = time.monotonic() - started
        combined = (completed.stdout or "") + (completed.stderr or "")
        teddy_dir = Path(project_dir) / ".teddy"
        sessions_dir = teddy_dir / "sessions"
        created_sessions = (
            sorted(path.name for path in sessions_dir.glob("*"))
            if sessions_dir.exists()
            else []
        )
        return {
            "case": label,
            "timed_out": False,
            "elapsed_seconds": round(elapsed, 2),
            "returncode": completed.returncode,
            "created_teddy_dir": teddy_dir.exists(),
            "created_sessions": created_sessions,
            "reached_opening_prompt": "What are we working on?" in combined,
            "saw_no_terminal_input_error": "No terminal input provided" in combined,
            "saw_configuration_error": "Configuration Error" in combined,
            "stdout_tail": (completed.stdout or "")[-800:],
            "stderr_tail": (completed.stderr or "")[-1400:],
        }


def main() -> None:
    results = [
        run_start_case("piped-stdin-no-api-key", None),
        run_start_case("piped-stdin-dummy-api-key", "dummy-key-for-probe"),
    ]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
