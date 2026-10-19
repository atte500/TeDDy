"""MRE: the first resumed turn shows ??? for context window and session cost.

Hypothesis under test:
1. `_sync_and_display_session_meta` clears `actual_model` in memory on resume but
   persists meta.yaml only when a model/api_key override changed a field.
2. Without an override the bare served `actual_model` stays on disk.
3. Planning telemetry prefers `actual_model`, which a fresh resume process does
   not know in the LiteLLM registry, so the window resolves to zero and both the
   context window and the session cost render as ??? / $???.

Run: uv run python spikes/debug/resume-telemetry-placeholders/01-resume-telemetry-placeholders-mre.py
Exit code 0 means the defect is reproduced.
"""

from __future__ import annotations

import sys
from typing import Any, Dict

import yaml

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _sync_and_display_session_meta,
)
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


class FakeLitellm:
    """Fresh resume process: the registry has not learned the served model yet."""

    def __init__(self) -> None:
        self.model_cost: Dict[str, Any] = {}


class CapturingUI:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def display_message(self, message: str) -> None:
        self.messages.append(message)


def repro_symptom_from_stale_actual_model() -> list[str]:
    """Real adapter plus real telemetry with an empty registry."""
    adapter = LiteLLMAdapter(
        config_service=FakeConfig(),
        hydrator=None,
        _litellm_provider=FakeLitellm(),
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
    meta = {
        "model": CONFIG_MODEL,
        "actual_model": SERVED_MODEL,
        "cumulative_cost": 0.05,
    }
    service._display_telemetry(meta, 56200)
    return ui.messages


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


def repro_resume_pop_not_persisted() -> tuple[bool, bool, int]:
    fs = InMemoryFS()
    fs.files[f"{TURN_DIR}/meta.yaml"] = seed_meta()
    _sync_and_display_session_meta(
        build_container(fs), "s-resume-probe", model=None, api_key=None
    )
    after_no_override = yaml.safe_load(fs.files[f"{TURN_DIR}/meta.yaml"])
    stale_kept = "actual_model" in after_no_override
    saves_without_override = len(fs.write_calls)

    fs2 = InMemoryFS()
    fs2.files[f"{TURN_DIR}/meta.yaml"] = seed_meta()
    _sync_and_display_session_meta(
        build_container(fs2), "s-resume-probe", model="override-model", api_key=None
    )
    after_override = yaml.safe_load(fs2.files[f"{TURN_DIR}/meta.yaml"])
    cleared_with_override = "actual_model" not in after_override
    return stale_kept, cleared_with_override, saves_without_override


def main() -> int:
    messages = repro_symptom_from_stale_actual_model()
    print("=== A. Telemetry with stale actual_model (real planning plus real adapter) ===")
    for message in messages:
        print(message)
    context_line = next(m for m in messages if "• Context:" in m)
    cost_line = next(m for m in messages if "• Session Cost:" in m)
    symptom_reproduced = "???" in context_line and "$???" in cost_line

    print("\n=== B. Resume clears actual_model in memory but not on disk ===")
    stale_kept, cleared_with_override, saves_without_override = (
        repro_resume_pop_not_persisted()
    )
    print(f"actual_model kept after no-override resume: {stale_kept}")
    print(f"save_meta calls without override: {saves_without_override}")
    print(f"actual_model cleared when a model override is given: {cleared_with_override}")

    if (
        symptom_reproduced
        and stale_kept
        and saves_without_override == 0
        and cleared_with_override
    ):
        print("\nDEFECT REPRODUCED")
        return 0
    print("\nDEFECT NOT REPRODUCED")
    return 1


if __name__ == "__main__":
    sys.exit(main())