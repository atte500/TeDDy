from unittest.mock import MagicMock
from tests.suites.acceptance.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.domain.models import RunStatus
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


def test_session_orchestrator_validation_failure_read_already_in_context(
    container, tmp_path
):
    """
    Integration test: SessionOrchestrator should catch READ validation failure
    and trigger the re-plan loop.
    """
    # Arrange
    container.register(
        IFileSystemManager,
        LocalFileSystemAdapter,
        root_dir=str(tmp_path),
    )
    # Resolve the use case which is mapped to SessionOrchestrator in container.py
    orchestrator = container.resolve(IRunPlanUseCase)

    session_dir = tmp_path / ".teddy" / "sessions" / "test-read"
    turn_01_dir = session_dir / "01"
    turn_01_dir.mkdir(parents=True)

    # Set up context
    (session_dir / "session.context").write_text("README.md", encoding="utf-8")
    (turn_01_dir / "turn.context").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text("content", encoding="utf-8")

    builder = MarkdownPlanBuilder("Faulty Plan")
    builder.add_action("READ", params={"Resource": "[README.md](/README.md)"})
    plan_path = turn_01_dir / "plan.md"
    plan_path.write_text(builder.build(), encoding="utf-8")

    # Mock LLM for planning
    planning_service = container.resolve(IPlanningUseCase)
    # The PlanningService uses generate_plan, not plan, in its implementation
    planning_service.generate_plan = MagicMock(return_value="Corrected Plan")

    # Ensure required turn artifacts exist for transition logic
    (turn_01_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")
    (turn_01_dir / "pathfinder.xml").write_text("<p>S</p>", encoding="utf-8")

    # Act
    report = orchestrator.execute(
        plan_content=plan_path.read_text(encoding="utf-8"), plan_path=str(plan_path)
    )

    # Assert
    assert report.run_summary.status == RunStatus.VALIDATION_FAILED
    assert "README.md is already in context" in report.validation_result[0]
    assert (session_dir / "02" / "plan.md").exists()


def test_session_orchestrator_validation_failure_edit_not_in_context(
    container, tmp_path
):
    """
    Integration test: SessionOrchestrator should catch EDIT validation failure.
    """
    # Arrange
    container.register(
        IFileSystemManager,
        LocalFileSystemAdapter,
        root_dir=str(tmp_path),
    )
    orchestrator = container.resolve(IRunPlanUseCase)

    session_dir = tmp_path / ".teddy" / "sessions" / "test-edit"
    turn_01_dir = session_dir / "01"
    turn_01_dir.mkdir(parents=True)

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("original", encoding="utf-8")
    (turn_01_dir / "turn.context").write_text("", encoding="utf-8")

    plan_content = """# Faulty Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
````text
### 1. Synthesis
Test

### 2. Justification
Test

### 3. Expected Outcome
Test

### 4. State Dashboard
Test
````

## Action Plan

### `EDIT`
- **File Path:** [src/main.py](/src/main.py)
- **Description:** Faulty edit.

#### `FIND:`
````python
original
````
#### `REPLACE:`
````python
new
````
"""
    plan_path = turn_01_dir / "plan.md"
    plan_path.write_text(plan_content, encoding="utf-8")
    (turn_01_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")
    (turn_01_dir / "pathfinder.xml").write_text("<p>S</p>", encoding="utf-8")

    # Act
    report = orchestrator.execute(plan_content=plan_content, plan_path=str(plan_path))

    # Assert
    assert report.run_summary.status == RunStatus.VALIDATION_FAILED
    assert (
        "src/main.py is not in the current turn context" in report.validation_result[0]
    )


def test_session_orchestrator_validation_failure_prune_not_in_context(
    container, tmp_path
):
    """
    Integration test: SessionOrchestrator should catch PRUNE validation failure.
    """
    # Arrange
    container.register(
        IFileSystemManager,
        LocalFileSystemAdapter,
        root_dir=str(tmp_path),
    )
    orchestrator = container.resolve(IRunPlanUseCase)

    session_dir = tmp_path / ".teddy" / "sessions" / "test-prune"
    turn_01_dir = session_dir / "01"
    turn_01_dir.mkdir(parents=True)

    (turn_01_dir / "turn.context").write_text("README.md", encoding="utf-8")

    plan_content = """# Faulty Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
````text
### 1. Synthesis
Test

### 2. Justification
Test

### 3. Expected Outcome
Test

### 4. State Dashboard
Test
````

## Action Plan

### `PRUNE`
- **Resource:** [src/main.py](/src/main.py)
- **Description:** Faulty prune.
"""
    plan_path = turn_01_dir / "plan.md"
    plan_path.write_text(plan_content, encoding="utf-8")
    (turn_01_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")
    (turn_01_dir / "pathfinder.xml").write_text("<p>S</p>", encoding="utf-8")

    # Act
    report = orchestrator.execute(plan_content=plan_content, plan_path=str(plan_path))

    # Assert
    assert report.run_summary.status == RunStatus.VALIDATION_FAILED
    assert (
        "src/main.py is not in the current turn context" in report.validation_result[0]
    )
