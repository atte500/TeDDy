"""Verification MRE (sandbox replica): blank `-m` prompts when a human is reachable.

Runs against the replica at
`spikes/debug/blank-resume-message-prompt/replica_session_lifecycle_manager.py`,
which applies the proposed fix: the blank-message prompt is gated on user
presence (a TTY is attached and the run is not a pipeline) instead of on the
action-approval flag (`interactive`, which is False whenever
`yolo_default: true`).

Scenarios (interactive=False i.e. yolo, blank `-m`):
  A. COMPLETE_TURN, TTY, not pipeline          -> prompts, reply drives planning.
  B. COMPLETE_TURN, no TTY, not pipeline       -> no prompt, blank -> absent.
  C. COMPLETE_TURN, TTY, pipeline=True         -> no prompt, blank -> absent.
  D. COMPLETE_TURN, TTY, not pipeline, empty   -> session terminates, no plan.
  E. PENDING await-reply, TTY, not pipeline    -> prompts, empty reply aborts.
  F. PENDING await-reply, no TTY, not pipeline -> no prompt, guidance fallback.

Exit 0 = fix verified, 1 = fix not verified.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from replica_session_lifecycle_manager import (  # noqa: E402
    SessionLifecycleManager,
    _NEXT_INSTRUCTION_PROMPT,
)
from teddy_executor.core.ports.outbound.session_manager import (  # noqa: E402
    SessionState,
)

TURN01 = ".teddy/sessions/20260417_120000-feature/01"
TURN02 = ".teddy/sessions/20260417_120000-feature/02"
_AWAITING_PROMPT = "The agent is awaiting your reply. How do you want to proceed?"


class FakeSystemEnvironment:
    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


class FakeInteractor:
    def __init__(self, reply: str) -> None:
        self.asked: list[str] = []
        self.messages: list[str] = []
        self._reply = reply

    def ask_question(self, prompt, resources=None, agent_name=None):
        self.asked.append(prompt)
        return self._reply

    def display_message(self, message):
        self.messages.append(message)


class FakeSessionService:
    def __init__(self) -> None:
        self._states = [
            (SessionState.COMPLETE_TURN, TURN01),
            (SessionState.PENDING_PLAN, TURN02),
        ]
        self.transitions: list[str] = []

    def get_session_state(self, name):
        return self._states.pop(0)

    def transition_to_next_turn(self, plan_path=None):
        self.transitions.append(plan_path)
        return TURN02

    def to_root_relative(self, turn_dir, filename):
        return f"{turn_dir}/{filename}"


class FakeAwaitingSessionService:
    """Session service double for a PENDING await-reply turn."""

    def __init__(self) -> None:
        self.meta_saves: list[tuple[str, dict]] = []

    def get_session_state(self, name):
        return (SessionState.PENDING_PLAN, TURN01)

    def load_turn_meta(self, turn_path):
        return {"awaiting_reply": True, "agent_name": "assistant"}

    def to_root_relative(self, turn_dir, filename):
        return f"{turn_dir}/{filename}"

    def save_turn_meta(self, path, meta):
        self.meta_saves.append((path, meta))


class FakeFileSystem:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str]] = []

    def path_exists(self, path):
        return True

    def read_file(self, path):
        return "Prior report body\n"

    def write_file(self, path, content):
        self.writes.append((path, content))


class FakePlanner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def trigger_new_plan(self, turn_dir, message=None):
        self.calls.append((turn_dir, message))
        return ("feature", None)


class FakeOrchestrator:
    def execute(self, **kwargs):
        return SimpleNamespace(plan_path=kwargs.get("plan_path"))


def build_manager(*, tty, reply, pipeline):
    interactor = FakeInteractor(reply)
    planner = FakePlanner()
    session_service = FakeSessionService()
    file_system = FakeFileSystem()
    ports = SimpleNamespace(
        session_service=session_service,
        file_system_manager=file_system,
        report_formatter=None,
        user_interactor=interactor,
        session_planner=planner,
        replanner=None,
        plan_parser=None,
        time_service=None,
        report_assembler=None,
        system_environment=FakeSystemEnvironment(tty),
    )
    manager = SessionLifecycleManager(ports)
    manager.tee_active = True  # keep the sandbox off the history.log Tee path
    return manager, interactor, planner, session_service, file_system


def run_scenario(*, tty, reply, pipeline):
    manager, interactor, planner, session_service, file_system = build_manager(
        tty=tty, reply=reply, pipeline=pipeline
    )
    result = manager.resume(
        session_name="feature",
        orchestrator=FakeOrchestrator(),
        interactive=False,  # yolo: action approval off, prompt must still fire
        message="",
        pipeline=pipeline,
    )
    return interactor, planner, session_service, file_system, result


def run_awaiting_scenario(*, tty, reply, pipeline):
    interactor = FakeInteractor(reply)
    session_service = FakeAwaitingSessionService()
    ports = SimpleNamespace(
        session_service=session_service,
        file_system_manager=FakeFileSystem(),
        report_formatter=None,
        user_interactor=interactor,
        session_planner=FakePlanner(),
        replanner=None,
        plan_parser=None,
        time_service=None,
        report_assembler=None,
        system_environment=FakeSystemEnvironment(tty),
    )
    manager = SessionLifecycleManager(ports)
    manager.tee_active = True
    result = manager.resume(
        session_name="feature",
        orchestrator=FakeOrchestrator(),
        interactive=False,  # yolo
        message="",
        pipeline=pipeline,
    )
    return interactor, session_service, result


def check(label, condition, detail):
    print(f"[{'PASS' if condition else 'FAIL'}] {label}: {detail}")
    return condition


def main() -> int:
    interactor, planner, session_service, _, result = run_scenario(
        tty=True, reply="Next step", pipeline=False
    )
    ok_a = all(
        [
            check(
                "A prompt fired under yolo with a TTY",
                interactor.asked == [_NEXT_INSTRUCTION_PROMPT],
                f"asked={interactor.asked}",
            ),
            check(
                "A reply forwarded to planning",
                planner.calls == [(TURN02, "Next step")],
                f"calls={planner.calls}",
            ),
            check(
                "A turn transitioned",
                session_service.transitions == [f"{TURN01}/plan.md"],
                f"transitions={session_service.transitions}",
            ),
            check(
                "A report returned",
                result[0] == "feature" and result[1] is not None,
                f"result={result}",
            ),
        ]
    )

    interactor, planner, _, _, _ = run_scenario(
        tty=False, reply="unused", pipeline=False
    )
    ok_b = all(
        [
            check(
                "B no prompt without a TTY",
                interactor.asked == [],
                f"asked={interactor.asked}",
            ),
            check(
                "B blank message normalizes to absent",
                planner.calls == [(TURN02, None)],
                f"calls={planner.calls}",
            ),
        ]
    )

    interactor, planner, _, _, _ = run_scenario(
        tty=True, reply="unused", pipeline=True
    )
    ok_c = all(
        [
            check(
                "C no prompt in pipeline mode",
                interactor.asked == [],
                f"asked={interactor.asked}",
            ),
            check(
                "C blank message normalizes to absent",
                planner.calls == [(TURN02, None)],
                f"calls={planner.calls}",
            ),
        ]
    )

    interactor, planner, session_service, _, result = run_scenario(
        tty=True, reply="", pipeline=False
    )
    ok_d = all(
        [
            check(
                "D prompt fired when a human is reachable",
                interactor.asked == [_NEXT_INSTRUCTION_PROMPT],
                f"asked={interactor.asked}",
            ),
            check(
                "D empty reply terminates the session",
                result == ("feature", None),
                f"result={result}",
            ),
            check(
                "D no next turn planned",
                planner.calls == [] and session_service.transitions == [],
                f"calls={planner.calls}, transitions={session_service.transitions}",
            ),
        ]
    )

    interactor, session_service, result = run_awaiting_scenario(
        tty=True, reply="", pipeline=False
    )
    ok_e = all(
        [
            check(
                "E awaiting-reply prompt fired under yolo with a TTY",
                interactor.asked == [_AWAITING_PROMPT],
                f"asked={interactor.asked}",
            ),
            check(
                "E empty reply terminates without consuming",
                result == ("feature", None) and session_service.meta_saves == [],
                f"result={result}, meta_saves={session_service.meta_saves}",
            ),
        ]
    )

    interactor, session_service, result = run_awaiting_scenario(
        tty=False, reply="unused", pipeline=False
    )
    ok_f = all(
        [
            check(
                "F no prompt without a TTY",
                interactor.asked == [],
                f"asked={interactor.asked}",
            ),
            check(
                "F guidance fallback shown",
                len(interactor.messages) == 1,
                f"messages={interactor.messages}",
            ),
            check(
                "F session exits cleanly",
                result == ("feature", None),
                f"result={result}",
            ),
        ]
    )

    if all([ok_a, ok_b, ok_c, ok_d, ok_e, ok_f]):
        print(
            "\nFIX VERIFIED: the prompt fires when a human is reachable, "
            "regardless of yolo, on both resume prompt sites."
        )
        return 0
    print("\nFIX NOT VERIFIED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
