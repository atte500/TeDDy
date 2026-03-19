import pytest
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


@pytest.fixture
def validator(container):
    return container.resolve(IPlanValidator)


@pytest.fixture
def parser(container):
    return container.resolve(IPlanParser)


def test_validate_rejects_edit_if_file_not_in_context(validator, parser, mock_fs):
    """
    PlanValidator.validate should return an error if an EDIT action
    targets a file not present in Session or Turn context.
    """
    # Given
    plan_content = (
        MarkdownPlanBuilder("Test Plan")
        .add_edit("src/main.py", find_replace="a", replace="b")
        .build()
    )
    plan = parser.parse(plan_content)

    # File exists on disk but is not in context
    mock_fs.path_exists.return_value = True
    mock_fs.read_file.return_value = "a"

    context_paths = {"Session": ["README.md"], "Turn": ["docs/ARCH.md"]}

    # When
    errors = validator.validate(plan, context_paths=context_paths)

    # Then
    assert len(errors) == 1
    assert "is not in the current turn context" in errors[0].message
    assert errors[0].file_path == "src/main.py"


def test_edit_validator_checks_context_before_existence(validator, parser, mock_fs):
    """
    To prevent leaking information about the filesystem, the EDIT validator
    must check if a file is in context BEFORE checking if it exists on disk.
    """
    # Given
    plan_content = (
        MarkdownPlanBuilder("Test Plan")
        .add_edit("secret/file.txt", find_replace="a", replace="b")
        .build()
    )
    plan = parser.parse(plan_content)

    # File does NOT exist on disk and is NOT in context
    mock_fs.path_exists.return_value = False
    context_paths = {"Session": [], "Turn": []}

    # When
    errors = validator.validate(plan, context_paths=context_paths)

    # Then: It should report 'not in context', not 'file does not exist'
    assert len(errors) == 1
    assert "is not in the current turn context" in errors[0].message


def test_validate_rejects_read_if_file_already_in_context(validator, parser, mock_fs):
    """
    PlanValidator.validate should return an error if a READ action
    targets a file already present in Session or Turn context.
    """
    # Given
    plan_content = MarkdownPlanBuilder("Test Plan").add_read("README.md").build()
    plan = parser.parse(plan_content)
    mock_fs.path_exists.return_value = True

    context_paths = {"Session": ["README.md"], "Turn": []}

    # When
    errors = validator.validate(plan, context_paths=context_paths)

    # Then
    assert len(errors) == 1
    assert "is already in context" in errors[0].message
    assert errors[0].file_path == "README.md"


def test_validate_rejects_prune_if_file_not_in_turn_context(validator, parser, mock_fs):
    """
    PlanValidator.validate should return an error if a PRUNE action
    targets a file NOT present in the Turn context.
    """
    # Given
    plan_content = MarkdownPlanBuilder("Test Plan").add_prune("README.md").build()
    plan = parser.parse(plan_content)

    context_paths = {"Session": ["README.md"], "Turn": ["src/main.py"]}

    # When
    errors = validator.validate(plan, context_paths=context_paths)

    # Then
    assert len(errors) == 1
    assert "is not in the current turn context" in errors[0].message
    assert errors[0].file_path == "README.md"
