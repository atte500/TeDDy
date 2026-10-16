"""Unit: the guardrail termination fallback uses neutral wording.

The limits apply to every non-interactive run, not only --yolo, so the
fallback reason must not claim the limit is --yolo-only.
"""

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _emit_guard_termination,
)


def test_guard_termination_fallback_uses_neutral_wording(capsys):
    """The fallback reason must not carry the stale --yolo-only wording."""
    _emit_guard_termination(None)

    captured = capsys.readouterr()

    assert "YOLO" not in captured.out, (
        "Fallback reason must not carry stale --yolo-only wording, "
        f"got: {captured.out!r}"
    )
    assert "guardrail limit reached" in captured.out.lower()
