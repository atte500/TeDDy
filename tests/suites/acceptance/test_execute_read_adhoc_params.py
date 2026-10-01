"""Acceptance tests for EXECUTE Tail override and READ Lines range (Slice 00-24)."""

import re
import sys
from pathlib import Path

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


class TestExecuteReadAdhocParams:
    """End-to-end tests for EXECUTE Tail and READ Lines parameters."""

    def test_execute_tail_limits_output(self, real_env, monkeypatch) -> None:
        """Verify EXECUTE with Tail=5 shows only last 5 lines + truncation hint."""
        # Arrange: create a script that outputs 20 lines
        workspace = Path(real_env.workspace)
        script = workspace / "gen_lines.py"
        script.write_text("import sys\nfor i in range(1, 21): print(f'Line {i}')\n")

        adapter = CliTestAdapter(monkeypatch, workspace)
        plan = (
            MarkdownPlanBuilder("Tail Test")
            .add_execute(
                f"{sys.executable} {script}",
                description="Generate 20 lines of output",
                expected_outcome="Lines 16-20 should appear",
                Tail=5,
            )
            .build()
        )

        # Act
        report = adapter.execute_plan(plan)

        # Assert
        assert report.summary.get("Overall Status") == "SUCCESS"
        execute_log = report.action_logs[0]
        assert execute_log.type == "EXECUTE"
        stdout = execute_log.details.get("stdout", "")
        lines = stdout.splitlines()
        # Should contain lines 16-20
        expected_lines = [f"Line {i}" for i in range(16, 21)]
        for expected in expected_lines:
            assert expected in lines, f"Expected '{expected}' in output"
        # Should NOT contain lines 1-15
        unexpected_lines = [f"Line {i}" for i in range(1, 16)]
        for unexpected in unexpected_lines:
            assert unexpected not in lines, f"'{unexpected}' should NOT appear (tail=5)"
        # Truncation hint should be present
        assert "truncated" in stdout.lower(), "Expected truncation hint"

    def test_read_lines_range(self, real_env, monkeypatch) -> None:
        """Verify READ with Lines=10-20 returns only that range.

        Line-scoped READ content renders inline inside its Action Log entry,
        exactly once, and is NOT duplicated under `## Resource Contents`.
        """
        # Arrange: create a file with 30 lines
        workspace = Path(real_env.workspace)
        file_path = workspace / "sample.txt"
        file_content = "\n".join(f"Line {i}" for i in range(1, 31)) + "\n"
        file_path.write_text(file_content)

        adapter = CliTestAdapter(monkeypatch, workspace)
        builder = MarkdownPlanBuilder("Read Lines Test")
        # MarkdownPlanBuilder.add_read does not support extra kwargs like Lines,
        # so we use add_action directly with the desired params dict.
        builder.add_action(
            "READ",
            {
                "Resource": builder._path_link("sample.txt"),
                "Description": "Read lines 10-20",
                "Lines": "10-20",
            },
        )
        plan = builder.build()

        # Act
        report = adapter.execute_plan(plan)

        # Assert
        assert report.summary.get("Overall Status") == "SUCCESS"
        # Line-scoped READ content renders inline inside its Action Log entry
        # and must NOT be duplicated under Resource Contents (render-placement
        # contract; see test_report_read_render_placement.py).
        resource_contents = report.extract_resource_contents()
        assert "sample.txt" not in resource_contents, (
            "Line-scoped READ content must not be rendered under Resource Contents"
        )
        # Extract every full content line ("Line N") rendered in the report.
        # Line-anchored matching prevents "Line 1" from substring-matching
        # "Line 10".."Line 19"; duplicates would indicate the content was
        # rendered more than once.
        rendered_numbers = re.findall(r"(?m)^Line (\d+)$", report.stdout)
        rendered_lines = sorted(int(n) for n in rendered_numbers)
        # Expect exactly lines 10-20, each rendered exactly once
        assert rendered_lines == list(range(10, 21)), (
            f"Expected exactly lines 10-20 once each, got {rendered_lines}"
        )
