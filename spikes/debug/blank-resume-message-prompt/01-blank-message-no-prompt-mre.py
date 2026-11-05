"""MRE: a blank `-m` on resume is silently dropped when `yolo_default: true`.

Expected (README): `teddy resume -m ""` prompts for a message.
Observed: planning starts immediately, no prompt.

Reproduction record: this script targets the PRE-FIX gate. After the
user-presence fix landed in `src/`, `_resolve_blank_message` takes
`pipeline` and requires the injected system-environment port, so the
script no longer runs against current production. MRE 02 is the fix
verification.

This drives the two exact inputs the resume path feeds into the prompt gate:

    interactive = not (_resolve_yolo(None, config) or pipeline)
    message, terminated = _resolve_blank_message('', interactive)

Exit codes: 0 = symptom reproduced, 1 = symptom did not reproduce.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from teddy_executor.__main__ import _resolve_yolo
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
    _NEXT_INSTRUCTION_PROMPT,
)


class RecordingInteractor:
    """Fake IUserInteractor that records whether the prompt was shown."""

    def __init__(self, reply: str = "") -> None:
        self.asked: list[str] = []
        self._reply = reply

    def ask_question(self, prompt, resources=None, agent_name=None):
        self.asked.append(prompt)
        return self._reply


class FakeConfig:
    def __init__(self, settings):
        self._settings = settings

    def get_setting(self, key, default=None):
        return self._settings.get(key, default)


class FakePorts:
    """Dummy SessionPorts object: only user_interactor is exercised."""

    def __init__(self, interactor):
        self.session_service = None
        self.file_system_manager = None
        self.report_formatter = None
        self.user_interactor = interactor
        self.session_planner = None
        self.replanner = None
        self.plan_parser = None
        self.time_service = None
        self.report_assembler = None


def main() -> int:
    config = FakeConfig({"yolo_default": True})
    yolo = _resolve_yolo(None, config)
    pipeline = False
    interactive = not (yolo or pipeline)

    interactor = RecordingInteractor()
    manager = SessionLifecycleManager(FakePorts(interactor))
    message, terminated = manager._resolve_blank_message("", interactive)

    print(f"yolo_default=True -> _resolve_yolo(None, config)={yolo}")
    print(f"interactive = not ({yolo} or {pipeline}) = {interactive}")
    print(
        f"_resolve_blank_message('', {interactive}) -> "
        f"message={message!r}, terminated={terminated}"
    )
    print(f"prompts issued: {interactor.asked}")

    control_interactor = RecordingInteractor(reply="")
    control_manager = SessionLifecycleManager(FakePorts(control_interactor))
    control_message, control_terminated = control_manager._resolve_blank_message("", True)
    print(
        "control _resolve_blank_message('', True) -> "
        f"message={control_message!r}, terminated={control_terminated}, "
        f"prompts={control_interactor.asked}"
    )
    control_ok = (
        control_interactor.asked == [_NEXT_INSTRUCTION_PROMPT]
        and control_message is None
        and control_terminated is True
    )

    reproduced = (
        interactive is False
        and message is None
        and terminated is False
        and interactor.asked == []
        and control_ok
    )
    if reproduced:
        print("SYMPTOM REPRODUCED: blank -m silently dropped, no prompt shown.")
        return 0
    print("SYMPTOM NOT REPRODUCED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
