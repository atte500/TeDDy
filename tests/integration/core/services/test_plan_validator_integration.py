from pathlib import Path


from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.services.plan_validator import PlanValidator


def test_create_fails_if_file_exists(tmp_path: Path):
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
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)

    fs_adapter = LocalFileSystemAdapter(root_dir=str(tmp_path))
    validator = PlanValidator(fs_adapter)

    # Act & Assert
    errors = validator.validate(plan)
    assert len(errors) == 1
    assert "File already exists" in errors[0].message


def test_read_fails_if_file_missing(tmp_path: Path):
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
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)

    fs_adapter = LocalFileSystemAdapter(root_dir=str(tmp_path))
    validator = PlanValidator(fs_adapter)

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert "File to read does not exist" in errors[0].message


def test_edit_fails_if_file_missing(tmp_path: Path):
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
    parser = MarkdownPlanParser()
    plan = parser.parse(plan_content)

    fs_adapter = LocalFileSystemAdapter(root_dir=str(tmp_path))
    validator = PlanValidator(fs_adapter)

    # Act
    errors = validator.validate(plan)

    # Assert
    assert len(errors) == 1
    assert "File to edit does not exist" in errors[0].message
