from datetime import datetime, timezone
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


def test_formatter_crashes_when_details_is_string():
    """
    Given an ActionLog where details is a string (not a dict),
    When the report is formatted,
    Then it should not raise an UndefinedError.
    """
    # Arrange
    formatter = MarkdownReportFormatter()
    report = ExecutionReport(
        plan_title="Crash Repro",
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        action_logs=[
            ActionLog(
                action_type="TEST",
                status=ActionStatus.SKIPPED,
                params={"foo": "bar"},
                details="This is a string detail, not a dict.",
            )
        ],
    )

    # Act
    # This should not raise
    output = formatter.format(report)

    # Assert
    assert "This is a string detail" in output


def test_repro_chat_with_user_headers_bug():
    """
    Reproduces a bug where H3 headers inside a CHAT_WITH_USER action
    are misidentified as new actions.
    """
    from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser

    parser = MarkdownPlanParser()
    plan_content = """# Phase 1: Problem Space Exploration
- **Status:** Green 🟢
- **Plan Type:** Synthesis
- **Agent:** Pathfinder

## Rationale
```text
Rationale content
```

## Action Plan

### `CHAT_WITH_USER`
Based on current developer sentiment...

### 1. The Best All-Rounder: **Godot Engine**
*   **Best For:** Most developers...

### 2. The Best for Rust: **Bevy**
*   **Best For:** Rust developers...
"""

    # This should parse as ONE action (CHAT_WITH_USER), containing the rest as content.
    # Currently it likely fails or parses "1. The Best All-Rounder..." as an unknown action.
    plan = parser.parse(plan_content)

    assert len(plan.actions) == 1
    assert plan.actions[0].type == "CHAT_WITH_USER"
    # The content is usually stripped of the header, so check for subsequent content
    # Note: CHAT_WITH_USER content handling might vary, but it should capture the markdown body
    # If the parser treats `### 1...` as a new action, `len(plan.actions)` will be > 1
    # or it will raise an InvalidPlanError for unknown action type.
