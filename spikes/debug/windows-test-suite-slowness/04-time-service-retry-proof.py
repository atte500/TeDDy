"""Prove that injecting a time service removes the real retry backoff sleeps.

Four litellm tests drive three failed completion attempts, so the adapter
sleeps 0.5s then 1.0s on the real clock. This probe builds the same adapter
twice, once without a time service and once with a recording fake, and shows
the wait disappears while the recorded delays match the backoff schedule.
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path("src").resolve()))

import litellm

from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter


class StaticConfig:
    """Minimal config double exposing only the llm section the adapter reads."""

    def __init__(self) -> None:
        self._settings: Dict[str, Any] = {
            "llm.model": "gpt-4o",
            "llm.api_key": "sk-test",  # pragma: allowlist secret
            "llm": {
                "model": "gpt-4o",
                "api_key": "sk-test",  # pragma: allowlist secret
                "max_retries": 3,
            },
        }

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)


class RecordingTimeService:
    """In-memory time service that records sleeps without waiting."""

    def __init__(self) -> None:
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def fail_completion(**kwargs: Any) -> Any:
    raise RuntimeError("API Failure")


def measure(label: str, time_service: Optional[RecordingTimeService]) -> None:
    adapter = LiteLLMAdapter(config_service=StaticConfig(), time_service=time_service)
    adapter._get_litellm()
    adapter._validated = True
    start = time.perf_counter()
    try:
        adapter.get_completion(
            messages=[{"role": "user", "content": "hi"}], model="gpt-4o"
        )
    except Exception as error:
        elapsed = time.perf_counter() - start
        print(f"{label}: {elapsed:.2f}s, raised {type(error).__name__}")
    if time_service is not None:
        print(f"{label}: recorded sleeps {time_service.sleeps}")


def main() -> None:
    litellm.completion = fail_completion
    measure("adapter without time service", None)
    measure("adapter with recording time service", RecordingTimeService())


if __name__ == "__main__":
    main()