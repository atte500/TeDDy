"""Acceptance tests for EXECUTE Tail override and READ Lines range (Slice 00-24)."""

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
        """Verify READ with Lines=10-20 returns only that range."""
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
        resource_contents = report.extract_resource_contents()
        # The resource key in the report should be "sample.txt" (relative path)
        content = resource_contents.get("sample.txt", "")
        lines = content.splitlines()
        # Expect exactly 11 lines (10 through 20 inclusive)
        expected_lines = [f"Line {i}" for i in range(10, 21)]
        assert len(lines) == len(expected_lines), (
            f"Expected {len(expected_lines)} lines, got {len(lines)}"
        )
        for expected in expected_lines:
            assert expected in lines, f"Expected '{expected}' in output"
        # Should NOT contain lines 1 or 30
        assert "Line 1" not in lines, "Line 1 should NOT appear"
        assert "Line 30" not in lines, "Line 30 should NOT appear"
