import pytest
from unittest.mock import MagicMock
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.domain.models import ProjectContext, ContextItem
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunStatus,
)
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.session_replanner import SessionReplanner


@pytest.fixture
def mock_context_service():
    return MagicMock(spec=IGetContextUseCase)


@pytest.fixture
def mock_config():
    service = MagicMock(spec=IConfigService)
    # Default config for auto-pruning
    service.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.global_context_threshold": 10000,
        "auto_pruning.prune_preceding_on_non_green": True,
        "auto_pruning.prune_validation_failures": True,
    }.get(key, default)
    return service


@pytest.fixture
def orchestrator(mock_context_service, mock_config):
    from teddy_executor.core.services.session_pruning_service import (
        SessionPruningService,
    )

    fs_mock = MagicMock(spec=IFileSystemManager)
    pruning_service = SessionPruningService(
        config_service=mock_config,
        file_system_manager=fs_mock,
    )

    mock_prompt_manager = MagicMock()
    mock_prompt_manager.fetch_system_prompt.return_value = "mock prompt"
    mock_llm_client = MagicMock()
    mock_llm_client.get_text_token_count.return_value = 100

    return SessionOrchestrator(
        execution_orchestrator=MagicMock(spec=IRunPlanUseCase),
        session_service=MagicMock(),
        file_system_manager=fs_mock,
        plan_validator=MagicMock(spec=IPlanValidator),
        plan_parser=MagicMock(spec=IPlanParser),
        user_interactor=MagicMock(spec=IUserInteractor),
        lifecycle_manager=MagicMock(),
        replanner=MagicMock(spec=SessionReplanner),
        context_service=mock_context_service,
        config_service=mock_config,
        llm_client=mock_llm_client,
        prompt_manager=mock_prompt_manager,
        pruning_service=pruning_service,
    )


def test_execute_prunes_deleted_files_heuristic(
    orchestrator, mock_context_service, mock_fs
):
    """
    Heuristic 5: Files with git status 'D' (Deleted) must be auto-pruned.
    """
    # Arrange
    plan_path = "session/02/plan.md"
    orchestrator._file_system_manager.path_exists.return_value = True  # Is session mode

    # Mock context with a deleted file
    items = [
        ContextItem(path="existing.py", token_count=100, git_status="", scope="Turn"),
        ContextItem(path="deleted.py", token_count=100, git_status="D", scope="Turn"),
    ]
    mock_context_service.get_context.return_value = ProjectContext(
        header="", content="", items=items
    )

    orchestrator._plan_parser.parse.return_value = MagicMock()
    orchestrator._plan_validator.validate.return_value = []

    # Act
    orchestrator.execute(plan_path=plan_path)

    # Assert
    # Verify ProjectContext was passed to execution_orchestrator
    call_args = orchestrator._execution_orchestrator.execute.call_args
    passed_context = call_args.kwargs.get("project_context")

    assert passed_context is not None
    # deleted.py should be pruned (selected=False)
    deleted_item = next(i for i in passed_context.items if i.path == "deleted.py")
    assert deleted_item.selected is False
    assert deleted_item.auto_prune_reason == "File deleted from disk"

    # existing.py should be untouched
    existing_item = next(i for i in passed_context.items if i.path == "existing.py")
    assert existing_item.selected is True


def test_execute_prunes_global_budget_heuristic(orchestrator, mock_context_service):
    """
    Heuristic 2: Prune largest files in 'Turn' scope if total exceeds budget.
    """
    # Arrange
    orchestrator._file_system_manager.path_exists.return_value = True
    orchestrator._config_service.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.global_context_threshold": 1000,
    }.get(key, default)

    items = [
        ContextItem(
            path="system.py", token_count=5000, git_status="", scope="System"
        ),  # Exempt
        ContextItem(path="large.py", token_count=800, git_status="", scope="Turn"),
        ContextItem(path="medium.py", token_count=300, git_status="", scope="Turn"),
        ContextItem(path="small.py", token_count=100, git_status="", scope="Turn"),
    ]
    # Total Turn = 1200. Threshold = 1000.
    # Must prune large.py (800) to get to 400.

    mock_context_service.get_context.return_value = ProjectContext(
        items=items, header="", content=""
    )
    orchestrator._plan_parser.parse.return_value = MagicMock()
    orchestrator._plan_validator.validate.return_value = []

    # Act
    orchestrator.execute(plan_path="session/02/plan.md")

    # Assert
    passed_context = orchestrator._execution_orchestrator.execute.call_args.kwargs.get(
        "project_context"
    )
    large = next(i for i in passed_context.items if i.path == "large.py")
    assert large.selected is False
    assert large.auto_prune_reason == "Pruned to fit context budget"

    # small and medium should be selected
    assert (
        next(i for i in passed_context.items if i.path == "medium.py").selected is True
    )
    assert (
        next(i for i in passed_context.items if i.path == "small.py").selected is True
    )


def test_execute_prunes_failure_history_heuristic(orchestrator, mock_context_service):
    """
    Heuristic 3: Prune preceding turn artifacts after a successful recovery.
    """
    # Arrange
    orchestrator._file_system_manager.path_exists.return_value = True

    # Turn 01 is 🔴, Turn 02 is 🟢
    items = [
        ContextItem(
            path="session/01/plan.md", token_count=100, git_status="", scope="Turn"
        ),
        ContextItem(
            path="session/01/report.md", token_count=100, git_status="", scope="Turn"
        ),
        ContextItem(
            path="session/02/plan.md", token_count=100, git_status="", scope="Turn"
        ),
        ContextItem(
            path="session/02/report.md", token_count=100, git_status="", scope="Turn"
        ),
    ]

    mock_context_service.get_context.return_value = ProjectContext(
        items=items, header="", content=""
    )

    def mock_read(path):
        if "01/plan.md" in path:
            return "- **Status:** [OUTCOME: FAILURE] [STATE: 🔴]"
        if "02/plan.md" in path:
            return "- **Status:** [OUTCOME: SUCCESS] [STATE: 🟢]"
        return ""

    orchestrator._file_system_manager.read_file.side_effect = mock_read

    orchestrator._plan_parser.parse.return_value = MagicMock()
    orchestrator._plan_validator.validate.return_value = []

    # Act
    orchestrator.execute(plan_path="session/02/plan.md")

    # Assert
    passed_context = orchestrator._execution_orchestrator.execute.call_args.kwargs.get(
        "project_context"
    )
    plan_item = next(i for i in passed_context.items if "01/plan.md" in i.path)
    report_item = next(i for i in passed_context.items if "01/report.md" in i.path)

    assert plan_item.selected is False
    assert report_item.selected is False
    assert (
        plan_item.auto_prune_reason
        == "Pruned failure history after successful recovery"
    )

    # Turn 02 should remain
    assert (
        next(i for i in passed_context.items if "02/plan.md" in i.path).selected is True
    )


def test_execute_prunes_validation_failure_heuristic(
    orchestrator, mock_context_service
):
    """
    Heuristic 4: Prune plan/report if report contains '- **Overall Status:** Validation Failed'.
    """
    # Arrange
    orchestrator._file_system_manager.path_exists.return_value = True

    items = [
        ContextItem(
            path="session/01/plan.md", token_count=100, git_status="", scope="Turn"
        ),
        ContextItem(
            path="session/01/report.md",
            token_count=100,
            git_status="",
            scope="Turn",
        ),
    ]

    mock_context_service.get_context.return_value = ProjectContext(
        items=items, header="", content=""
    )

    # Mock file system to return validation failure in report (using spec-compliant string)
    def mock_read(path):
        if "01/report.md" in path:
            return "- **Overall Status:** Validation Failed"
        return ""

    orchestrator._file_system_manager.read_file.side_effect = mock_read

    orchestrator._plan_parser.parse.return_value = MagicMock()
    orchestrator._plan_validator.validate.return_value = []

    # Act
    orchestrator.execute(plan_path="session/02/plan.md")

    # Assert
    passed_context = orchestrator._execution_orchestrator.execute.call_args.kwargs.get(
        "project_context"
    )
    plan_item = next(i for i in passed_context.items if "01/plan.md" in i.path)
    report_item = next(i for i in passed_context.items if "01/report.md" in i.path)

    assert plan_item.selected is False
    assert report_item.selected is False
    assert plan_item.auto_prune_reason == "Plan failed validation"


def test_execute_respects_manually_pruned_files_during_transition(
    orchestrator, mock_context_service
):
    """
    Integration: Orchestrator must pass pruned paths to LifecycleManager for manifest removal.
    """
    # Arrange
    plan_path = "session/02/plan.md"
    orchestrator._file_system_manager.path_exists.return_value = True  # Is session mode

    plan = MagicMock(spec=Plan)
    plan.metadata = {"pruned_context": "docs/stale.md,tests/temp.py"}

    orchestrator._plan_parser.parse.return_value = plan
    orchestrator._plan_validator.validate.return_value = []

    # Mock context
    mock_context_service.get_context.return_value = ProjectContext(
        items=[], header="", content=""
    )

    # Mock execution outcome
    report = MagicMock(spec=ExecutionReport)
    # Ensure status allows finalization (not aborted)
    # Based on SessionOrchestrator logic: report.run_summary.status
    # We setup the nested mock explicitly
    report.run_summary = MagicMock()
    report.run_summary.status = RunStatus.SUCCESS
    orchestrator._execution_orchestrator.execute.return_value = report

    # Act
    orchestrator.execute(plan_path=plan_path)

    # Assert
    # The orchestrator should have passed the plan (containing pruning metadata) to finalize_turn
    orchestrator._lifecycle_manager.finalize_turn.assert_called_once()
    kwargs = orchestrator._lifecycle_manager.finalize_turn.call_args.kwargs
    assert kwargs["plan"] == plan
