from pathlib import Path
import pytest
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
from teddy_executor.core.domain.models.execution_report import RunStatus
from teddy_executor.core.ports.outbound import IFileSystemManager
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator


@pytest.fixture
def integration_container(container, tmp_path):
    """Configures the container for integration testing with a real temporary FS."""
    fs_adapter = LocalFileSystemAdapter(
        edit_simulator=container.resolve(IEditSimulator), root_dir=str(tmp_path)
    )
    container.register(IFileSystemManager, instance=fs_adapter)
    return container


def test_missing_replace_block_trace_placement_integration(
    integration_container, tmp_path: Path
):
    """
    Scenario A Integration: Verify mismatch indicator placement in the exception message.
    """
    target_file = tmp_path / "app.py"
    target_file.write_text("print('hello')\n", encoding="utf-8")

    plan_content = """# Test Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Test.
### 2. Justification
Test.
### 3. Expected Outcome
Test.
### 4. State Dashboard
Test.
```

## Action Plan

### `EDIT`
- File Path: [app.py](/app.py)
- Description: Missing replace block.

#### `FIND:`
```python
print('hello')
```

This paragraph is NOT a REPLACE heading.
"""
    orchestrator = integration_container.resolve(IRunPlanUseCase)

    with pytest.raises(InvalidPlanError) as excinfo:
        orchestrator.execute(plan_content=plan_content, interactive=False)

    error_msg = str(excinfo.value)
    assert "Missing REPLACE block after FIND block" in error_msg
    assert 'Paragraph: "This paragraph is NOT a REPLACE heading."' in error_msg
    assert "[✗]" in error_msg


def test_multiple_find_matches_hint_integration(integration_container, tmp_path: Path):
    """
    Scenario B Integration: Verify multiple FIND matches hint in the failed report.
    """
    target_file = tmp_path / "app.py"
    target_file.write_text("dup\ndup\n", encoding="utf-8")

    plan_content = """# Test Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
```text
### 1. Synthesis
Test.
### 2. Justification
Test.
### 3. Expected Outcome
Test.
### 4. State Dashboard
Test.
```

## Action Plan

### `EDIT`
- File Path: [app.py](/app.py)
- Description: Ambiguous edit.

#### `FIND:`
```text
dup
```
#### `REPLACE:`
```text
new
```
"""
    orchestrator = integration_container.resolve(IRunPlanUseCase)
    report = orchestrator.execute(plan_content=plan_content, interactive=False)

    assert report.run_summary.status == RunStatus.VALIDATION_FAILED
    full_errors = "\n".join(report.validation_result or [])
    assert "The `FIND` block is ambiguous" in full_errors
    assert "**Hint:**" in full_errors


def test_code_fence_backtick_count_in_trace_integration(integration_container):
    """
    Scenario C Integration: Verify backtick counts in the AST trace within the exception message.
    """
    plan_content = """# Incomplete Plan
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
`````text
### 1. Synthesis
Rationale with 5 backticks.
`````

### `INVALID`
- Node here.
"""
    orchestrator = integration_container.resolve(IRunPlanUseCase)

    with pytest.raises(InvalidPlanError) as excinfo:
        orchestrator.execute(plan_content=plan_content, interactive=False)

    assert "Code Block (5 backticks)" in str(excinfo.value)
