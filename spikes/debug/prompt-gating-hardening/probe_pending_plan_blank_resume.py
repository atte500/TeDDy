"""Record today's behaviour for a present-but-blank `-m` on a non-awaiting
PENDING_PLAN resume.

The manager is driven with recording doubles so the orchestrator call shape,
any prompt, and the terminated flag are observable without a real session.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from teddy_executor.core.ports.outbound.session_manager import SessionState
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)

TURN_PATH = "/tmp/teddy-probe/.teddy/sessions/feature/03"


class RecordingInteractor:
    def __init__(self) -> None:
        self.asked: list[str] = []
        self.messages: list[str] = []

    def ask_question(self, prompt, resources=None, agent_name=None):
        self.asked.append(prompt)
        return "unused-reply"

    def display_message(self, message: str) -> None:
        self.messages.append(message)


class RecordingOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return "EXECUTION_REPORT"


class FakeFileSystem:
    def path_exists(self, path: str) -> bool:
        return False


def run_case(label: str, message, isatty: bool) -> dict:
    interactor = RecordingInteractor()
    orchestrator = RecordingOrchestrator()
    ports = SimpleNamespace(
        session_service=SimpleNamespace(
            get_session_state=lambda name: (SessionState.PENDING_PLAN, TURN_PATH),
            load_turn_meta=lambda path: {},
            to_root_relative=lambda turn_dir, filename: f"{turn_dir}/{filename}",
        ),
        file_system_manager=FakeFileSystem(),
        report_formatter=None,
        user_interactor=interactor,
        session_planner=None,
        replanner=None,
        plan_parser=None,
        time_service=None,
        report_assembler=None,
        system_environment=SimpleNamespace(isatty=lambda: isatty),
    )
    manager = SessionLifecycleManager(ports=ports)
    result = manager.resume(
        session_name="feature",
        orchestrator=orchestrator,
        require_approval=False,
        pipeline=False,
        message=message,
    )
    return {
        "case": label,
        "message_repr": repr(message),
        "isatty": isatty,
        "asked_prompts": interactor.asked,
        "displayed_messages": interactor.messages,
        "orchestrator_calls": orchestrator.calls,
        "result": [result[0], result[1]],
    }


def main() -> None:
    cases = [
        run_case("blank -m at a terminal", "", True),
        run_case("blank -m without a terminal", "", False),
        run_case("absent -m at a terminal", None, True),
    ]
    print(json.dumps(cases, indent=2))


if __name__ == "__main__":
    main()
