"""Probe the blank-message channel on a non-awaiting PENDING_PLAN resume.

Three facts, all driven against the real SessionLifecycleManager.resume:

1. Today a blank ``-m ""`` does not prompt and runs the pending plan through
   the bare ``execute(plan_path=...)`` path.
2. Today a non-blank ``-m`` seeds ``plan.metadata["user_request"]`` and runs the
   SAME plan object via ``execute(plan=plan)``. That metadata is exactly what
   the TUI ``m`` key reads and what the report assembler turns into
   ``## User Request``.
3. With the proposed one-call fix -- resolve a blank message through the SAME
   ``_resolve_blank_message`` the EMPTY/COMPLETE_TURN branches use -- a blank
   ``-m`` prompts when a human is reachable, seeds the reply into the plan
   metadata, and runs the seeded plan, for interactive and yolo runs alike,
   while the no-terminal and empty-reply paths stay safe.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from teddy_executor.core.ports.outbound.session_manager import SessionState
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
    _NEXT_INSTRUCTION_PROMPT,
)

TURN_PATH = "/tmp/teddy-probe/.teddy/sessions/feature/03"
PLAN_PATH = f"{TURN_PATH}/plan.md"


class FakePlan:
    """Minimal plan double: the branch only touches metadata and the
    communication-turn predicate."""

    def __init__(self) -> None:
        self.metadata: dict = {}

    def is_communication_turn(self) -> bool:
        return False


class RecordingInteractor:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.asked: list[str] = []
        self.messages: list[str] = []

    def ask_question(self, prompt, resources=None, agent_name=None):
        self.asked.append(prompt)
        return self.reply

    def display_message(self, message: str) -> None:
        self.messages.append(message)


class RecordingOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return {"report": "ok"}


class FakeFileSystem:
    def __init__(self) -> None:
        self.files = {PLAN_PATH: "plan body"}

    def path_exists(self, path: str) -> bool:
        return path in self.files

    def read_raw_file(self, path: str) -> str:
        return self.files.get(path, "")

    def read_file(self, path: str) -> str:
        return self.files.get(path, "")


class FakeParser:
    def __init__(self, plan: FakePlan) -> None:
        self._plan = plan

    def parse(self, content: str, plan_path=None):
        return self._plan


def build_manager(manager_cls, message, isatty, reply):
    interactor = RecordingInteractor(reply)
    orchestrator = RecordingOrchestrator()
    plan = FakePlan()
    ports = SimpleNamespace(
        session_service=SimpleNamespace(
            get_session_state=lambda name: (SessionState.PENDING_PLAN, TURN_PATH),
            load_turn_meta=lambda path: {},
            to_root_relative=lambda turn_dir, filename: f"{turn_dir}/{filename}",
            save_turn_meta=lambda *a, **k: None,
            preserve_turn_in_session_context=lambda *a, **k: None,
        ),
        file_system_manager=FakeFileSystem(),
        report_formatter=None,
        user_interactor=interactor,
        session_planner=None,
        replanner=None,
        plan_parser=FakeParser(plan),
        time_service=None,
        report_assembler=None,
        system_environment=SimpleNamespace(isatty=lambda: isatty),
    )
    return manager_cls(ports=ports), interactor, orchestrator, plan


class FixedManager(SessionLifecycleManager):
    """The real manager with the proposed one-call fix in the pending branch."""

    def resume(  # noqa: PLR0913
        self,
        session_name,
        orchestrator,
        require_approval=True,
        project_context=None,
        pipeline=False,
        message=None,
    ):
        state, turn_path = self._session_service.get_session_state(session_name)
        assert state == SessionState.PENDING_PLAN, state
        turn_meta = self._session_service.load_turn_meta(turn_path)
        plan_path = f"{turn_path}/plan.md"
        plan = self._parse_pending_plan(turn_path, plan_path, message)
        if self._should_consume_awaiting_reply(turn_meta, plan):
            return self._consume_awaiting_reply(
                turn_path,
                turn_meta,
                session_name,
                orchestrator,
                require_approval,
                project_context=project_context,
                pipeline=pipeline,
                message=message,
                plan=plan,
            )
        # THE FIX: resolve a present-but-blank message into a prompt, exactly as
        # the EMPTY/COMPLETE_TURN branches already do.
        message, terminated = self._resolve_blank_message(message, pipeline)
        if terminated:
            return (session_name, None)
        if message and plan is None:
            plan = self._parse_pending_plan(turn_path, plan_path, message)
        if plan is not None:
            plan.metadata["user_request"] = message
            report = orchestrator.execute(
                plan=plan,
                plan_path=plan_path,
                require_approval=require_approval,
                project_context=project_context,
                pipeline=pipeline,
            )
        else:
            report = orchestrator.execute(
                plan_path=plan_path,
                require_approval=require_approval,
                project_context=project_context,
                pipeline=pipeline,
            )
            self._record_reply_on_resumed_turn(turn_path, message)
        return (session_name, report)


def run_case(label, manager_cls, message, isatty, reply="", require_approval=True):
    manager, interactor, orchestrator, _plan = build_manager(
        manager_cls, message, isatty, reply
    )
    result = manager.resume(
        session_name="feature",
        orchestrator=orchestrator,
        require_approval=require_approval,
        pipeline=False,
        message=message,
    )
    calls = [
        {
            "has_plan": "plan" in call,
            "plan_path": call.get("plan_path"),
            "require_approval": call.get("require_approval"),
            "seeded_user_request": getattr(call.get("plan"), "metadata", {}).get(
                "user_request"
            ),
        }
        for call in orchestrator.calls
    ]
    return {
        "label": label,
        "message": repr(message),
        "reply": repr(reply),
        "isatty": isatty,
        "require_approval": require_approval,
        "asked_prompts": interactor.asked,
        "execute_calls": calls,
        "result": [result[0], result[1]],
    }


def main() -> None:
    cases = [
        run_case("real: blank -m, terminal", SessionLifecycleManager, "", True),
        run_case(
            "real: non-blank -m, terminal",
            SessionLifecycleManager,
            "refactor auth",
            True,
        ),
        run_case(
            "fixed: blank -m, terminal (interactive)",
            FixedManager,
            "",
            True,
            reply="refactor auth",
            require_approval=True,
        ),
        run_case(
            "fixed: blank -m, terminal (yolo)",
            FixedManager,
            "",
            True,
            reply="refactor auth",
            require_approval=False,
        ),
        run_case("fixed: blank -m, no terminal", FixedManager, "", False),
        run_case(
            "fixed: blank -m, terminal, empty reply",
            FixedManager,
            "",
            True,
            reply="",
        ),
    ]
    print(json.dumps({"next_prompt": _NEXT_INSTRUCTION_PROMPT, "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
