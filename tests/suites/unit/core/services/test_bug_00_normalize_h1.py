"""
Regression test for bug: missing space after # in H1 heading.
Verifies that #Title is normalized to # Title before parsing.
"""

import pytest

from teddy_executor.core.services.parser_infrastructure import (
    normalize_headings,
)


# --- Unit tests for normalize_headings function ---


class TestNormalizeHeadings:
    def test_first_line_no_space(self):
        """#Title -> # Title"""
        result = normalize_headings("#Test Plan Title\n- **Status:** Green 🟢")
        assert result == "# Test Plan Title\n- **Status:** Green 🟢"

    def test_first_line_with_space(self):
        """# Title (already correct) -> unchanged"""
        result = normalize_headings("# Test Plan Title\n- **Status:** Green 🟢")
        assert result == "# Test Plan Title\n- **Status:** Green 🟢"

    def test_no_change_on_second_line(self):
        """Only first line is normalized; lines inside code fences untouched."""
        content = (
            "#Test\n"
            "- **Status:** Green 🟢\n"
            "## Rationale\n"
            "~~~~~~\n"
            "some text\n"
            "#!/bin/bash\n"
            "~~~~~~\n"
        )
        result = normalize_headings(content)
        # First line normalized
        assert result.startswith("# Test\n")
        # Shebang inside fence remains unchanged
        assert "#!/bin/bash" in result

    def test_single_line_no_newline(self):
        """Content with no newline at all (only one line)."""
        result = normalize_headings("#Title")
        assert result == "# Title"

    def test_heading_with_h2_no_space(self):
        """##Title (no space) on first line: no change (first-line-only normalization targets single #)."""
        result = normalize_headings("##Title\nsome text")
        assert result == "##Title\nsome text"


# --- Integration test for the full parser with #Title ---


@pytest.fixture
def parser(container):
    """Fixture providing a real IPlanParser instance."""
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser

    return container.resolve(IPlanParser)


class TestParserIntegration:
    def test_parser_handles_no_space_h1(self, parser):
        """The parser should successfully parse a plan with #Title (no space)."""
        raw = (
            "#My Plan Title\n"
            "- **Status:** Green 🟢\n"
            "- **Plan Type:** Implementation\n"
            "- **Agent:** Debugger\n"
            "\n"
            "## Rationale\n"
            "~~~~~~\n"
            "1. Synthesis\n"
            "just testing\n"
            "~~~~~~\n"
            "\n"
            "## Action Plan\n"
            "\n"
            "### `EXECUTE`\n"
            "- **Description:** Test\n"
            "- **Expected Outcome:** success\n"
            "~~~~~~shell\n"
            "echo hello\n"
            "~~~~~~\n"
        )
        plan = parser.parse(raw)
        assert plan.title == "My Plan Title"
        assert len(plan.actions) == 1
        assert plan.raw_content.startswith("# My Plan Title")

    def test_parser_still_handles_correct_h1(self, parser):
        """Existing # Title (with space) continues to work."""
        raw = (
            "# My Plan Title\n"
            "- **Status:** Green 🟢\n"
            "- **Plan Type:** Implementation\n"
            "- **Agent:** Debugger\n"
            "\n"
            "## Rationale\n"
            "~~~~~~\n"
            "1. Synthesis\n"
            "just testing\n"
            "~~~~~~\n"
            "\n"
            "## Action Plan\n"
            "\n"
            "### `EXECUTE`\n"
            "- **Description:** Test\n"
            "- **Expected Outcome:** success\n"
            "~~~~~~shell\n"
            "echo hello\n"
            "~~~~~~\n"
        )
        plan = parser.parse(raw)
        assert plan.title == "My Plan Title"
        assert len(plan.actions) == 1

    def test_parser_writes_corrected_content_to_file(self, parser, tmp_path):
        """When plan_path points to a session file and heading is missing space, file is overwritten with corrected content."""

        # Simulate a session file path
        session_dir = tmp_path / ".teddy" / "sessions" / "test-session"
        turn_dir = session_dir / "01"
        turn_dir.mkdir(parents=True)
        plan_file = turn_dir / "plan.md"

        original = (
            "Some preamble text before the H1.\n\n"
            "#My Plan Title\n"
            "- **Status:** Green 🟢\n"
            "- **Plan Type:** Implementation\n"
            "- **Agent:** Debugger\n"
            "\n"
            "## Rationale\n"
            "~~~~~~\n"
            "1. Synthesis\n"
            "just testing\n"
            "~~~~~~\n"
            "\n"
            "## Action Plan\n"
            "\n"
            "### `EXECUTE`\n"
            "- **Description:** Test\n"
            "- **Expected Outcome:** success\n"
            "~~~~~~shell\n"
            "echo hello\n"
            "~~~~~~\n"
        )
        plan_file.write_text(original, encoding="utf-8")

        # Parse with plan_path set (simulates session mode)
        plan = parser.parse(original, plan_path=str(plan_file))

        # Read the file after parsing
        corrected = plan_file.read_text(encoding="utf-8")
        assert corrected.startswith("# My Plan Title"), "Heading should be corrected"
        assert "Some preamble text" not in corrected, "Preamble should be stripped"
        assert corrected == plan.raw_content, "File should match raw_content"

    def test_parser_does_not_overwrite_if_content_unchanged(self, parser, tmp_path):
        """When heading is already correct and no preamble, file should not be overwritten (idempotent)."""

        session_dir = tmp_path / ".teddy" / "sessions" / "test-session"
        turn_dir = session_dir / "01"
        turn_dir.mkdir(parents=True)
        plan_file = turn_dir / "plan.md"

        original = (
            "# My Plan Title\n"
            "- **Status:** Green 🟢\n"
            "- **Plan Type:** Implementation\n"
            "- **Agent:** Debugger\n"
            "\n"
            "## Rationale\n"
            "~~~~~~\n"
            "1. Synthesis\n"
            "just testing\n"
            "~~~~~~\n"
            "\n"
            "## Action Plan\n"
            "\n"
            "### `EXECUTE`\n"
            "- **Description:** Test\n"
            "- **Expected Outcome:** success\n"
            "~~~~~~shell\n"
            "echo hello\n"
            "~~~~~~\n"
        )
        plan_file.write_text(original, encoding="utf-8")

        # Parse with plan_path set
        plan = parser.parse(original, plan_path=str(plan_file))

        # File should remain the same (no write needed because content is already correct)
        after = plan_file.read_text(encoding="utf-8")
        assert after == original
