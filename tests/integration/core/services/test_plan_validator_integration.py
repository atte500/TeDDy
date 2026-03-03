from pathlib import Path
import pytest

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound import IFileSystemManager
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.services.plan_validator import PlanValidator
from teddy_executor.core.services.validation_rules.create import CreateActionValidator
from teddy_executor.core.services.validation_rules.edit import EditActionValidator
from teddy_executor.core.services.validation_rules.execute import ExecuteActionValidator
from teddy_executor.core.services.validation_rules.read import ReadActionValidator


@pytest.fixture
def setup_container(container, tmp_path):
    """Configures the container for integration testing with a real temporary FS."""
    # Register missing parser
    container.register(IPlanParser, MarkdownPlanParser)

    # Create FS adapter with real simulator and test-specific root
    edit_simulator = container.resolve(IEditSimulator)
    fs_adapter = LocalFileSystemAdapter(
        edit_simulator=edit_simulator, root_dir=str(tmp_path)
    )
    container.register(IFileSystemManager, instance=fs_adapter)

    # Re-register validator graph to ensure they use the test FS adapter
    container.register(CreateActionValidator)
    container.register(EditActionValidator)
    container.register(ExecuteActionValidator)
    container.register(ReadActionValidator)

    container.register(
        IPlanValidator,
        PlanValidator,
        validators=[
            container.resolve(CreateActionValidator),
            container.resolve(EditActionValidator),
            container.resolve(ExecuteActionValidator),
            container.resolve(ReadActionValidator),
        ],
    )
    return container


def test_create_fails_if_file_exists(setup_container, tmp_path: Path):
    """
    Given a plan to CREATE a file that already exists,
    When the plan is validated,
    Then it should fail with a PlanValidationError.
    """
    # Arrange
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("content")

    plan_content = f"""
# Test Create Existing
- **Status:** Green 🟢
- **Plan Type:** Test
- **Agent:** Test Agent

## Rationale
````text
Dummy rationale for test.
````

## Action Plan

### `CREATE`
- **File Path:** [{existing_file.name}](/{existing_file.name})
- **Description:** Attempt to overwrite an existing file.
````text
new content
````
"""
    parser = setup_container.resolve(IPlanParser)
    plan = parser.parse(plan_content)
    validator = setup_container.resolve(IPlanValidator)

    # Act & Assert
    errors = validator.validate(plan)
    assert len(errors) == 1
    assert "File already exists" in errors[0].message


def test_read_fails_if_file_missing(setup_container, tmp_path: Path):
    """READ action fails if the local file does not exist."""
    # Arrange
    plan_content = (
        """
# Test
- **Status:** Green 🟢
- **Plan Type:** Test
- **Agent:** Test Agent

## Rationale
"""
        + "````text\nRationale.\n````"
        + """

## Action Plan
### `READ`
- **Resource:** [/missing.txt]
- **Description:** Read it
"""
    )
    parser = setup_container.resolve(IPlanParser)
    plan = parser.parse(plan_content)
    validator = setup_container.resolve(IPlanValidator)

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert "File to read does not exist" in errors[0].message


def test_edit_fails_if_file_missing(setup_container, tmp_path: Path):
    """EDIT action fails if the target file does not exist."""
    # Arrange
    plan_content = """
# Test Edit Missing
- **Status:** Green 🟢
- **Plan Type:** Test
- **Agent:** Test Agent

## Rationale
````text
Rationale.
````

## Action Plan
### `EDIT`
- **File Path:** [/missing.txt](/missing.txt)
- **Description:** Edit it

#### `FIND:`
`````text
old
`````
#### `REPLACE:`
`````text
new
`````
"""
    parser = setup_container.resolve(IPlanParser)
    plan = parser.parse(plan_content)
    validator = setup_container.resolve(IPlanValidator)

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert "File to edit does not exist" in errors[0].message
