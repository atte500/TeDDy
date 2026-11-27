"""Action-log headlines for MOVE and DELETE in the execution report.

The report is the audit trail a reviewer reads after a turn, so a rename must
name both of its paths and a removal must name what it removed. Both verbs
previously fell through to a link-form fallback that resolves a single path:
DELETE survived only because it carries ``path``, while MOVE carries
``source``/``destination`` and rendered an empty link as its headline.
"""

from datetime import datetime, timezone

import pytest

from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)

_TIMESTAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)
_MOVE_PARAMS = {
    "source": "src/app/old_name.py",
    "destination": "src/app/new_name.py",
}


def _render(action_type: str, params: dict) -> str:
    """Renders one successful action through the real formatter."""
    report = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS, start_time=_TIMESTAMP, end_time=_TIMESTAMP
        ),
        plan_title="Headline",
        action_logs=[
            ActionLog(
                status=ActionStatus.SUCCESS, action_type=action_type, params=params
            )
        ],
    )
    return MarkdownReportFormatter().format(report)


def test_move_headline_names_both_paths_in_plan_order():
    rendered = _render("MOVE", _MOVE_PARAMS)

    assert "### `MOVE`: src/app/old_name.py -> src/app/new_name.py" in rendered
    assert "[](" not in rendered


def test_move_headline_does_not_repeat_the_pair_in_the_body():
    rendered = _render("MOVE", _MOVE_PARAMS)

    assert "- **Source:**" not in rendered
    assert "- **Destination:**" not in rendered


@pytest.mark.parametrize(
    ("path", "expected_headline", "expected_bullet"),
    [
        pytest.param(
            "docs/notes/scratch.md",
            "### `DELETE`: scratch.md",
            "- **File Path:** `docs/notes/scratch.md`",
            id="nested-file",
        ),
        pytest.param(
            "docs/notes",
            "### `DELETE`: notes",
            "- **File Path:** `docs/notes`",
            id="directory",
        ),
        pytest.param(
            "scratch.md",
            "### `DELETE`: scratch.md",
            None,
            id="root-level-file",
        ),
    ],
)
def test_delete_headline_uses_the_file_action_form(
    path: str, expected_headline: str, expected_bullet: str | None
):
    rendered = _render("DELETE", {"path": path})

    assert expected_headline in rendered
    if expected_bullet:
        assert expected_bullet in rendered


def test_delete_headline_keeps_the_recursive_flag_visible():
    rendered = _render("DELETE", {"path": "src/app/legacy", "recursive": True})

    assert "- **Recursive:** True" in rendered


def test_path_less_verb_renders_its_bare_headline():
    rendered = _render("PROMPT", {"prompt": "Continue?"})

    assert "### `PROMPT`" in rendered
    assert "[](" not in rendered
