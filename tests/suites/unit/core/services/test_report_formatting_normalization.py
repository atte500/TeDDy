"""Core normalization of non-MESSAGE report action-log rendering."""

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

TS = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)


def _format(*logs: ActionLog, failed_resources=None) -> str:
    report = ExecutionReport(
        plan_title="Formatting Normalization",
        run_summary=RunSummary(status=RunStatus.SUCCESS, start_time=TS, end_time=TS),
        action_logs=list(logs),
        failed_resources=failed_resources or {},
    )
    return MarkdownReportFormatter().format(report)


def test_create_renders_basename_headline_and_full_path_bullet() -> None:
    output = _format(
        ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="CREATE",
            params={"File Path": "src/new_module.py", "Description": "Create it"},
        )
    )

    assert "### `CREATE`: new_module.py" in output
    assert "- **File Path:** `src/new_module.py`" in output
    assert "- **Description:** Create it" in output


def test_read_renders_basename_headline_and_full_path_bullet() -> None:
    output = _format(
        ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="READ",
            params={"File Path": "docs/spec.md"},
            details={"content": "hello"},
        )
    )

    assert "### `READ`: spec.md" in output
    assert "- **File Path:** `docs/spec.md`" in output


def test_create_without_path_renders_bare_header() -> None:
    output = _format(
        ActionLog(status=ActionStatus.SUCCESS, action_type="CREATE", params={})
    )

    assert "### `CREATE`\n" in output
    assert "### `CREATE`:" not in output


def test_execute_renders_plain_subject_without_quotes() -> None:
    output = _format(
        ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="EXECUTE",
            params={"description": "Say hi", "command": "echo hi"},
        )
    )

    assert "### `EXECUTE`: Say hi" in output
    assert '"Say hi"' not in output


def test_execute_without_description_renders_bare_header() -> None:
    output = _format(
        ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="EXECUTE",
            params={"command": "echo hi"},
        )
    )

    assert "### `EXECUTE`\n" in output
    assert "Execute Command" not in output


def test_research_renders_plain_subject() -> None:
    output = _format(
        ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="RESEARCH",
            params={"description": "Find docs"},
        )
    )

    assert "### `RESEARCH`: Find docs" in output


def test_url_resource_renders_full_url_without_file_path_bullet() -> None:
    output = _format(
        ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="READ",
            params={"Resource": "https://example.com/x"},
            details={"content": "hello"},
        )
    )

    assert "### `READ`: https://example.com/x" in output
    assert "- **File Path:**" not in output


def test_root_level_path_renders_basename_without_file_path_bullet() -> None:
    output = _format(
        ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="READ",
            params={"Resource": "README.md"},
            details={"content": "hello"},
        )
    )

    assert "### `READ`: README.md" in output
    assert "- **File Path:**" not in output


def test_single_resource_contents_section_when_both_sources_populated() -> None:
    failed_log = ActionLog(
        status=ActionStatus.FAILURE,
        action_type="CREATE",
        params={"File Path": "src/broken.py"},
        details={"error": "boom", "content": "broken contents"},
    )

    output = _format(
        failed_log, failed_resources={"src/also.py": "failed resource contents"}
    )

    assert output.count("## Resource Contents") == 1
    assert "broken contents" in output
    assert "failed resource contents" in output


def test_expected_outcome_is_title_case() -> None:
    output = _format(
        ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="EXECUTE",
            params={"command": "echo hi", "expected_outcome": "prints hi"},
        )
    )

    assert "- **Expected Outcome:** prints hi" in output
    assert "- **Expected outcome:**" not in output


def test_unrecognized_mapping_details_render_as_fenced_json() -> None:
    output = _format(
        ActionLog(
            status=ActionStatus.SUCCESS,
            action_type="CREATE",
            params={"File Path": "x.py"},
            details={"weird_key": "value", "count": 3},
        )
    )

    assert "```json" in output
    assert '"weird_key"' in output
    assert "value" in output
