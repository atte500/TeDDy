"""MRE: the editor-open state survives a terminal reply and leaks the draft file.

The reported defect needs one ask-loop instance to serve two turns, exactly as
the interactive session does. This script drives that instance directly:

1. Turn 1: press ``e`` so the GUI editor spawns, then answer in the terminal.
2. Turn 2: observe which prompt is rendered and whether the draft survived.

Only the terminal boundary and the editor process are simulated.

Set ``TEDDY_MRE_TARGET=replica`` to run the same scenario against the fixed
sandbox replica instead of the production module.
"""
from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from typing import Callable, Iterable
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))

_MRE_TARGET = os.environ.get("TEDDY_MRE_TARGET", "production")
if _MRE_TARGET == "replica":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import replica_console_interactor_ask_loop as _ask_loop_module  # noqa: E402
else:
    import teddy_executor.adapters.outbound.console_interactor_ask_loop as _ask_loop_module  # noqa: E402

ConsoleAskLoop = _ask_loop_module.ConsoleAskLoop
_ASK_LOOP_MODULE = _ask_loop_module.__name__

from teddy_executor.core.utils.editor_names import is_cli_editor  # noqa: E402
_EDITOR_OPENED_PREFIX = "Editor opened."
_DRAFT_BODY = (
    "draft typed in the editor\n"
    "\n"
    "<!-- Please enter your response above this line. -->\n"
    "\n"
    "turn 1 prompt\n"
)


def _make_loop() -> tuple[ConsoleAskLoop, str]:
    draft_path = os.path.join(
        tempfile.mkdtemp(prefix="teddy-editor-state-"), "draft.md"
    )

    system_env = MagicMock()
    system_env.create_temp_file.return_value = draft_path

    def _delete(path: str) -> None:
        if os.path.exists(path):
            os.remove(path)

    system_env.delete_file.side_effect = _delete

    tooling = MagicMock()
    tooling.find_editor.return_value = ["codium"]

    return ConsoleAskLoop(system_env, tooling), draft_path


def _drive(
    loop: ConsoleAskLoop,
    prompt: str,
    replies: Iterable[str],
    on_editor_spawn: Callable[..., None] | None = None,
) -> tuple[str, list[str]]:
    """Runs one ask-loop turn with scripted terminal replies."""
    rendered: list[str] = []
    queue = iter(replies)

    def _reply(prompt_text: str, **_kwargs: object) -> str:
        rendered.append(prompt_text)
        return next(queue, "")

    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch.object(ConsoleAskLoop, "_is_tty", return_value=True)
        )
        stack.enter_context(
            patch.object(ConsoleAskLoop, "_flush_stdin", return_value=None)
        )
        stack.enter_context(
            patch(f"{_ASK_LOOP_MODULE}.ptk_prompt", side_effect=_reply)
        )
        if on_editor_spawn is not None:
            stack.enter_context(
                patch("subprocess.Popen", side_effect=on_editor_spawn)
            )
        response = loop.run(prompt)

    return response, rendered


def main() -> int:
    loop, draft_path = _make_loop()

    def _save_draft(*_args, **_kwargs) -> None:
        with open(draft_path, "w", encoding="utf-8") as handle:
            handle.write(_DRAFT_BODY)

    first_response, first_prompts = _drive(
        loop, "turn 1 prompt", ["e", "ok give me command again"], _save_draft
    )
    draft_exists_after_turn_one = os.path.exists(draft_path)

    second_response, second_prompts = _drive(
        loop, "turn 2 prompt", ["fresh terminal answer"]
    )

    print("target module:", _MRE_TARGET)
    print("codium classified as CLI editor:", is_cli_editor(["codium"]))
    print("turn 1 prompts:", first_prompts)
    print("turn 1 response:", repr(first_response))
    print("turn 1 draft exists:", draft_exists_after_turn_one)
    print("turn 2 prompts:", second_prompts)
    print("turn 2 response:", repr(second_response))
    print("turn 2 active editor path:", loop._active_editor_path)
    print("turn 2 draft exists:", os.path.exists(draft_path))

    stale_prompt = bool(second_prompts) and second_prompts[0].startswith(
        _EDITOR_OPENED_PREFIX
    )
    draft_leaked = os.path.exists(draft_path)

    print("stale editor prompt on turn 2:", stale_prompt)
    print("draft file leaked:", draft_leaked)

    expect_fix = _MRE_TARGET == "replica"

    if stale_prompt and draft_leaked:
        print("VERDICT: defect reproduced.")
        return 1 if expect_fix else 0

    print("VERDICT: defect not reproduced.")
    return 0 if expect_fix else 1


if __name__ == "__main__":
    raise SystemExit(main())