"""Verify the candidate resume fix from the sandbox replica.

Proves:
1. The no-override resume now persists meta.yaml and removes `actual_model`.
2. The following telemetry, against a registry that knows the configured model,
   resolves the context window and the session cost instead of ??? and $???.

Run: uv run python spikes/debug/resume-telemetry-placeholders/02-verify-replica-fix.py
Exit code 0 means the fix is verified.
"""

from __future__ import annotations

import sys
from typing import Any, Dict

import yaml

from replica_session_cli_handlers import _sync_and_display_session_meta
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.core.domain.models.planning_ports import PlanningPorts
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
from teddy_executor.core.services.planning_service import PlanningService
from teddy_executor.core.services.session_repository import SessionRepository

CONFIG_MODEL = "openrouter/~deepseek/deepseek-flash-latest:nitro"
SERVED_MODEL = "deepseek/deepseek-v4.1-flash-1017"
TURN_DIR = ".teddy/sessions/s-resume-probe/05"


class FakeConfig:
    def get_setting(self, key: str, default: Any = None) -> Any:
        if key == "llm.model":
            return CONFIG_MODEL
        return default


class SeededLitellm:
    """A registry that already knows the configured model with its pricing."""

    def __init__(self) -> None:
        self.model_cost: Dict[str, Any] = {
            CONFIG_MODEL: {
                "max_input_tokens": 131072,
                "input_cost_per_token": 0.000001,
                "output_cost_per_token": 0.000002,
            }
        }


class CapturingUI:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def display_message(self, message: str) -> None:
        self.messages.append(message)


class InMemoryFS:
    def __init__(self) -> None:
        self.files: Dict[str, str] = {}
        self.write_calls: list[str] = []

    def path_exists(self, path: str) -> bool:
        return path in self.files

    def read_file(self, path: str) -> str:
        return self.files[path]

    def write_file(self, path: str, content: str) -> None:
        self.files[path] = content
        self.write_calls.append(path)


class FakeSessionManager:
    def get_latest_turn(self, session_name: str) -> str:
        return TURN_DIR


class ContainerStub:
    def __init__(self, mapping: Dict[Any, Any]) -> None:
        self._mapping = mapping

    def resolve(self, cls: Any, **kwargs: Any) -> Any:
        if cls in self._mapping:
            return self._mapping[cls]
        raise KeyError(f"No stub registered for {cls!r}")


def seed_meta() -> str:
    return yaml.dump(
        {
            "agent_name": "debugger",
            "model": CONFIG_MODEL,
            "actual_model": SERVED_MODEL,
            "cumulative_cost": 0.05,
        }
    )


def build_container(fs: InMemoryFS) -> ContainerStub:
    repository = SessionRepository(fs)  # type: ignore[arg-type]
    return ContainerStub(
        {
            ISessionManager: FakeSessionManager(),
            ISessionRepository: repository,
            IConfigService: FakeConfig(),
        }
    )


def run_telemetry(meta: Dict[str, Any]) -> list[str]:
    adapter = LiteLLMAdapter(
        config_service=FakeConfig(),
        hydrator=None,
        _litellm_provider=SeededLitellm(),
    )
    ui = CapturingUI()
    service = PlanningService(
        PlanningPorts(
            context=None,
            llm=adapter,
            fs=None,
            config=FakeConfig(),
            prompts=None,
            ui=ui,
            session_manager=None,
        )
    )
    service._display_telemetry(meta, 56200)
    return ui.messages


def main() -> int:
    fs = InMemoryFS()
    fs.files[f"{TURN_DIR}/meta.yaml"] = seed_meta()

    _sync_and_display_session_meta(
        build_container(fs), "s-resume-probe", model=None, api_key=None
    )
    persisted = yaml.safe_load(fs.files[f"{TURN_DIR}/meta.yaml"])

    saved = len(fs.write_calls) == 1
    cleared = "actual_model" not in persisted
    print("=== A. No-override resume under the replica fix ===")
    print(f"save_meta calls without override: {len(fs.write_calls)}")
    print(f"actual_model persisted after resume: {persisted.get('actual_model')}")

    messages = run_telemetry(persisted)
    print("\n=== B. Telemetry after the persisted clear ===")
    for message in messages:
        print(message)
    context_line = next(m for m in messages if "• Context:" in m)
    cost_line = next(m for m in messages if "• Session Cost:" in m)
    window_ok = "???" not in context_line and "131.1k" in context_line
    cost_ok = "$???" not in cost_line and "$0.0500" in cost_line

    if saved and cleared and window_ok and cost_ok:
        print("\nREPLICA FIX VERIFIED")
        return 0
    print("\nREPLICA FIX NOT VERIFIED")
    return 1


if __name__ == "__main__":
    sys.exit(main())