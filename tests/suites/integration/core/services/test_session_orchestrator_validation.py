from tests.harness.setup.mocking import POSIXPathMock
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
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
    # Mock LLM to pass preflight check
    mock_llm = POSIXPathMock()
    mock_llm.validate_config.return_value = []
    container.register(ILlmClient, instance=mock_llm)

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
    planning_service.generate_plan = POSIXPathMock(return_value="Corrected Plan")

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
    # Mock LLM to pass preflight check
    mock_llm = POSIXPathMock()
    mock_llm.validate_config.return_value = []
    container.register(ILlmClient, instance=mock_llm)

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
    # Mock LLM to pass preflight check
    mock_llm = POSIXPathMock()
    mock_llm.validate_config.return_value = []
    container.register(ILlmClient, instance=mock_llm)

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


def test_session_orchestrator_validation_replan_preserves_user_request_integration(
    container, tmp_path
):
    """
    Integration test: Ensure that when validation fails, the orchestrator
    transitions to next turn with is_replan: True, preserves the original
    human user_request throughout the replan generation, and saves it in metadata.
    """
    import yaml

    # Arrange
    container.register(
        IFileSystemManager,
        LocalFileSystemAdapter,
        root_dir=str(tmp_path),
    )
    # Mock LLM to simulate successful generation during replan
    mock_llm = POSIXPathMock()
    mock_llm.validate_config.return_value = []
    mock_llm.get_token_count.return_value = 50
    mock_llm.get_context_window.return_value = 128000
    mock_llm.get_completion_cost.return_value = 0.01

    # Simulate LLM response choices
    mock_choice = POSIXPathMock()
    mock_choice.message.content = "# Corrected Plan\n- **Status:** Green"
    mock_response = POSIXPathMock()
    mock_response.choices = [mock_choice]
    mock_llm.get_completion.return_value = mock_response

    container.register(ILlmClient, instance=mock_llm)

    orchestrator = container.resolve(IRunPlanUseCase)

    session_dir = tmp_path / ".teddy" / "sessions" / "test-wiring"
    turn_01_dir = session_dir / "01"
    turn_01_dir.mkdir(parents=True)

    # Set up Turn 01 metadata with user_request
    meta_content = {
        "turn_id": "01",
        "agent_name": "pathfinder",
        "user_request": "Implement feature X",
        "cumulative_cost": 0.05,
    }
    (turn_01_dir / "meta.yaml").write_text(yaml.dump(meta_content), encoding="utf-8")
    (turn_01_dir / "pathfinder.xml").write_text(
        "<prompt>System Prompt</prompt>", encoding="utf-8"
    )

    # Set up context
    (session_dir / "session.context").write_text("README.md", encoding="utf-8")
    (turn_01_dir / "turn.context").write_text("", encoding="utf-8")
    (tmp_path / "README.md").write_text("content", encoding="utf-8")

    # Faulty plan (READ file already in context)
    builder = MarkdownPlanBuilder("Faulty Plan")
    builder.add_action("READ", params={"Resource": "[README.md](/README.md)"})
    plan_path = turn_01_dir / "plan.md"
    plan_path.write_text(builder.build(), encoding="utf-8")

    # Act
    report = orchestrator.execute(
        plan_content=plan_path.read_text(encoding="utf-8"), plan_path=str(plan_path)
    )

    # Assert
    assert report.run_summary.status == RunStatus.VALIDATION_FAILED

    # Verify Turn 02 was created and has the correct plan.md
    turn_02_dir = session_dir / "02"
    assert turn_02_dir.exists()
    assert (turn_02_dir / "plan.md").exists()
    assert "# Corrected Plan" in (turn_02_dir / "plan.md").read_text(encoding="utf-8")

    # Verify Turn 02 metadata preserves the original human user_request
    turn_02_meta = yaml.safe_load(
        (turn_02_dir / "meta.yaml").read_text(encoding="utf-8")
    )
    assert turn_02_meta.get("is_replan") is True
    assert turn_02_meta.get("user_request") == "Implement feature X"
