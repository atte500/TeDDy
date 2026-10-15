"""Structural guard: the retired "Initial Request:" terminal label cannot return.

Slice 00-37 (User Message Terminal Echo), Cleanup deliverable.

Every terminal echo of a user's message is single-sourced through
``emit_user_message`` and uses the exact label "User Message:". The retired
"Initial Request:" label must not reappear in any production module. The guard
matches the exact WITH-colon label so it stays blind to the legitimate,
out-of-scope ``initial_request.md`` display name in ``core/utils/markdown.py``
(which carries no colon).
"""

from pathlib import Path

import teddy_executor


def _production_python_files() -> list[Path]:
    """All Python modules shipped in the production package."""
    package_root = Path(teddy_executor.__file__).parent
    return sorted(package_root.rglob("*.py"))


def test_retired_initial_request_label_absent_from_production() -> None:
    """No production module may contain the retired 'Initial Request:' label."""
    # Build the needle at runtime so this test does not itself carry the
    # retired literal (defence-in-depth; production is the scanned scope).
    retired_label = "Initial" + " Request:"
    offenders = [
        str(path)
        for path in _production_python_files()
        if retired_label in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        "The retired terminal label must not appear in any production module; "
        f"offenders: {offenders}"
    )
