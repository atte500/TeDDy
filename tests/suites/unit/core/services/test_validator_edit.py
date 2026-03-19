import pytest
from unittest.mock import MagicMock

from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound import IConfigService
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.services.plan_validator import PlanValidator
from teddy_executor.core.services.validation_rules.create import CreateActionValidator
from teddy_executor.core.services.validation_rules.edit import EditActionValidator
from teddy_executor.core.services.validation_rules.execute import ExecuteActionValidator
from teddy_executor.core.services.validation_rules.read import ReadActionValidator
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


@pytest.fixture
def parser(container) -> IPlanParser:
    """Provides a wired MarkdownPlanParser."""
    container.register(IPlanParser, MarkdownPlanParser)
    return container.resolve(IPlanParser)


@pytest.fixture
def validator(container, mock_fs) -> IPlanValidator:
    """Resolves the PlanValidator from the container with all rules."""
    mock_config = MagicMock()
    mock_config.get_setting.return_value = 0.95
    container.register(IConfigService, instance=mock_config)

    rules = [
        CreateActionValidator,
        EditActionValidator,
        ExecuteActionValidator,
        ReadActionValidator,
    ]
    for rule in rules:
        container.register(rule)

    container.register(
        IPlanValidator,
        PlanValidator,
        validators=[container.resolve(rule) for rule in rules],
    )
    return container.resolve(IPlanValidator)


def _p(parser, builder):
    """Helper to parse a plan from a builder."""
    return parser.parse(builder.build())


def test_validate_edit_action_with_nonexistent_find_block(parser, validator, mock_fs):
    """Verify error when FIND block content does not exist."""
    file_path = "app/test.txt"
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "Hello world"

    plan = _p(
        parser,
        MarkdownPlanBuilder("Test").add_edit(
            file_path, "Goodbye world", "Hello pytest"
        ),
    )
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "The `FIND` block could not be located in the file" in errors[0].message


def test_validate_edit_action_with_nonexistent_file(parser, validator, mock_fs):
    """Verify error when editing a non-existent file."""
    mock_fs.path_exists.return_value = False
    plan = _p(
        parser, MarkdownPlanBuilder("Test").add_edit("nonexistent.txt", "any", "thing")
    )
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "File to edit does not exist" in errors[0].message


def test_validate_edit_action_with_valid_find_block(parser, validator, mock_fs):
    """Verify success when FIND block content exists."""
    file_path = "app/test.txt"
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "Hello world"

    plan = _p(
        parser,
        MarkdownPlanBuilder("Test").add_edit(file_path, "Hello world", "Hello pytest"),
    )
    errors = validator.validate(plan)

    assert len(errors) == 0


def test_validate_edit_fails_if_find_block_not_unique(parser, validator, mock_fs):
    """Verify error when FIND block is ambiguous."""
    content = "def foo():\n    pass\n\ndef foo():\n    pass\n"
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = content

    plan = _p(
        parser,
        MarkdownPlanBuilder("Test").add_edit(
            "source.py", "def foo():\n    pass\n", "bar"
        ),
    )
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "ambiguous" in errors[0].message.lower()


def test_validate_edit_reports_multiple_failures(parser, validator, mock_fs):
    """Verify all failing edits are reported."""
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "Some content"

    plan = _p(
        parser,
        MarkdownPlanBuilder("Test").add_edit(
            "test.txt", [("Bad1", "G1"), ("Bad2", "G2")]
        ),
    )
    errors = validator.validate(plan)

    expected_error_count = 2
    assert len(errors) == expected_error_count
    assert "Bad1" in errors[0].message
    assert "Bad2" in errors[1].message


def test_validate_edit_provides_diff_on_mismatch(container, parser, validator, mock_fs):
    """Verify error message contains a diff on near-match."""
    container.resolve(IConfigService).get_setting.return_value = 0.99
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "This is the original content"

    plan = _p(
        parser,
        MarkdownPlanBuilder("Test").add_edit(
            "t.txt", "This is the orignal content", "New"
        ),
    )
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "- This is the orignal content" in errors[0].message
    assert "+ This is the original content" in errors[0].message


def test_validate_edit_diff_handling_no_trailing_newline(parser, validator, mock_fs):
    """Verify diff formatting for content without trailing newlines."""
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "Line with typo"

    plan = _p(
        parser,
        MarkdownPlanBuilder("Test").add_edit(
            "test.txt", "Line with typo extra", "fixed"
        ),
    )
    errors = validator.validate(plan)

    assert len(errors) == 1
    diff_content = errors[0].message.split("diff\n")[1].split("\n```")[0]
    min_lines = 3
    lines = diff_content.splitlines()
    assert len(lines) >= min_lines
    assert lines[0].startswith("-")
    assert lines[1].startswith("?")
    assert lines[2].startswith("+")


def test_validate_edit_fails_if_find_and_replace_identical(parser, validator, mock_fs):
    """Verify error when FIND and REPLACE are identical."""
    mock_fs.path_exists.return_value = True
    plan = _p(parser, MarkdownPlanBuilder("T").add_edit("s.py", "same", "same"))
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert "FIND and REPLACE blocks are identical" in errors[0].message


def test_validate_edit_provides_hint_if_replace_block_already_present(
    parser, validator, mock_fs
):
    """Verify hint when REPLACE block is already present but FIND is not."""
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "This is the New content"

    plan = _p(
        parser,
        MarkdownPlanBuilder("T").add_edit("a.py", "This is the Old content", "New"),
    )
    errors = validator.validate(plan)

    assert len(errors) == 1
    assert (
        "Hint:** The FIND block was not found, but the REPLACE block is already present"
        in errors[0].message
    )
