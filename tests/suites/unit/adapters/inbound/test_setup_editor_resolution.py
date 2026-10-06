"""Unit tests for the ``_resolve_setup_editor`` decision table (Slice 00-26).

The Wiring deliverable computes the one-time editor-setup signal at the CLI
boundary as::

    setup_editor = system_env.isatty() and not pipeline and (interactive or message is None)

The happy-path flip (a yolo session without ``-m`` on a TTY still runs the
editor setup) is proven end-to-end by the Acceptance Tracer Bullet. Per Rule 11
the SKIP permutations are edge cases, so they are pinned here at the Unit layer
against the single source of the decision, independently of the higher-level
CLI test. The ``TestEnvironment`` harness supplies a deterministic
``ISystemEnvironment.isatty()`` double toggled via ``with_tty``.
"""

import pytest

from teddy_executor.__main__ import _resolve_setup_editor
from teddy_executor.core.ports.outbound import ISystemEnvironment


@pytest.mark.parametrize(
    "interactive, message, pipeline, isatty, expected",
    [
        # start (interactive, the opening prompt will fire) on a TTY -> run.
        (True, None, False, True, True),
        # start -m (interactive approval loop) on a TTY -> run.
        (True, "x", False, True, True),
        # yolo without -m on a TTY (still blocks on the opening prompt) -> run (FIX).
        (False, None, False, True, True),
        # fully-specified batch -y -m on a TTY reads nothing -> skip.
        (False, "x", False, True, False),
        # pipeline run on a TTY -> skip.
        (False, "x", True, True, False),
        # any run with non-TTY stdin -> skip.
        (False, None, False, False, False),
        (True, None, False, False, False),
    ],
)
def test_resolve_setup_editor_decision_table(
    env, interactive, message, pipeline, isatty, expected
):
    env.with_tty(isatty)

    system_env = env.get_service(ISystemEnvironment)
    result = _resolve_setup_editor(
        system_env,
        interactive=interactive,
        message=message,
        pipeline=pipeline,
    )

    assert result is expected
