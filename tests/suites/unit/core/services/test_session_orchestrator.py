from datetime import datetime, timezone
from unittest.mock import ANY, MagicMock  # noqa: TID251
import pytest
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_replanner import SessionReplanner
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.mocking import register_mock


@pytest.fixture
def orchestrator(  # noqa: PLR0913
    container,
    mock_run_plan,
    mock_session_manager,
    mock_fs,
    mock_plan_validator,
    mock_plan_parser,
    mock_user_interactor,
):
    from tests.harness.setup.mocking import register_mock
    from teddy_executor.core.services.session_lifecycle_manager import (
        SessionLifecycleManager,
    )

    # Manually instantiate sub-services using the container to resolve ports
    replanner = SessionReplanner(
        file_system_manager=container.resolve(IFileSystemManager),
        planning_service=container.resolve(IPlanningUseCase),
    )

    from teddy_executor.core.ports.outbound.config_service import IConfigService
    from teddy_executor.core.ports.inbound.get_context_use_case import (
        IGetContextUseCase,
    )
    from teddy_executor.core.ports.outbound.llm_client import ILlmClient
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager

    from teddy_executor.core.services.session_pruning_service import (
        SessionPruningService,
    )

    # Instantiate the orchestrator with its dependencies
    mock_pruning_service = register_mock(container, SessionPruningService)
    mock_prompt_manager = register_mock(container, IPromptManager)
    mock_prompt_manager.fetch_system_prompt.return_value = "mock prompt content"
    mock_llm_client = register_mock(container, ILlmClient)
    mock_llm_client.get_text_token_count.return_value = 100
    mock_context_service = register_mock(container, IGetContextUseCase)

    orchestrator_instance = SessionOrchestrator(
        execution_orchestrator=container.resolve(IRunPlanUseCase),
        session_service=container.resolve(ISessionManager),
        file_system_manager=container.resolve(IFileSystemManager),
        plan_validator=container.resolve(IPlanValidator),
        plan_parser=container.resolve(IPlanParser),
        user_interactor=container.resolve(IUserInteractor),
        lifecycle_manager=register_mock(container, SessionLifecycleManager),
        replanner=replanner,
        context_service=mock_context_service,
        config_service=container.resolve(IConfigService),
        llm_client=mock_llm_client,
        prompt_manager=mock_prompt_manager,
        pruning_service=mock_pruning_service,
    )

    # Register as instances to bypass punq auto-wiring for untyped constructors
    container.register(SessionReplanner, instance=replanner)
    container.register(SessionOrchestrator, instance=orchestrator_instance)

    return orchestrator_instance


def test_session_orchestrator_triggers_transition_on_success(  # noqa: PLR0913
    orchestrator,
    mock_run_plan,
    mock_fs,
    mock_plan_parser,
    mock_plan_validator,
    container,
):
    """
    SessionOrchestrator should call SessionLifecycleManager.finalize_turn
    after successful plan execution.
    """
    # Arrange
    # Mock successful execution
    mock_run_plan.execute.return_value = ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
        plan_title="Test Plan",
        rationale="Test Rationale",
    )

    plan_content = MarkdownPlanBuilder("Test").build()
    plan_path = "path/to/01/plan.md"

    mock_fs.path_exists.return_value = True

    # Mock parsing and validation to allow execution flow
    from teddy_executor.core.domain.models import Plan

    mock_plan = register_mock(container, Plan)
    mock_plan.metadata = {}
    mock_plan_parser.parse.return_value = mock_plan
    mock_plan_validator.validate.return_value = []

    # Act
    orchestrator.execute(plan_content=plan_content, plan_path=plan_path)

    # Assert
    # Verify execution was called
    mock_run_plan.execute.assert_called_once()

    # Verify delegation to lifecycle manager
    orchestrator._lifecycle_manager.finalize_turn.assert_called_once_with(
        plan_path, mock_run_plan.execute.return_value, plan=ANY
    )


def test_session_orchestrator_passes_status_to_pruning_service(  # noqa: PLR0913
    orchestrator,
    mock_run_plan,
    mock_fs,
    mock_plan_parser,
    mock_plan_validator,
    container,
):
    """
    Wiring: SessionOrchestrator should pass the status from plan metadata to the pruning service.
    """
    # Arrange
    from teddy_executor.core.domain.models import Plan

    mock_plan = register_mock(container, Plan)
    mock_plan.metadata = {"Status": "SUCCESS 🟢"}
    mock_plan.is_session = True

    # Setup execution mocks
    mock_plan_parser.parse.return_value = mock_plan
    mock_plan_validator.validate.return_value = []
    mock_fs.path_exists.return_value = True  # For is_session_mode

    # Return context
    orchestrator._context_service.get_context.return_value = MagicMock()

    # Act
    orchestrator.execute(plan_path="path/to/01/plan.md", interactive=True)

    # Assert
    orchestrator._pruning_service.prune.assert_called_once_with(
        ANY, current_status="SUCCESS 🟢"
    )


def test_session_orchestrator_resolves_context_when_non_interactive(
    orchestrator,
    mock_run_plan,
    mock_fs,
    mock_plan_parser,
    mock_plan_validator,
):
    """
    SessionOrchestrator should resolve project context and call the pruning service
    even in non-interactive sessions.
    """
    # Arrange
    from teddy_executor.core.domain.models import Plan

    mock_plan = MagicMock(spec=Plan)
    mock_plan.metadata = {"Status": "SUCCESS 🟢"}
    mock_plan.is_session = True

    # Setup execution mocks
    mock_plan_parser.parse.return_value = mock_plan
    mock_plan_validator.validate.return_value = []
    mock_fs.path_exists.return_value = True  # For is_session_mode

    # Return context
    orchestrator._context_service.get_context.return_value = MagicMock()

    # Act
    orchestrator.execute(plan_path="path/to/01/plan.md", interactive=False)

    # Assert
    orchestrator._context_service.get_context.assert_called_once()
    orchestrator._pruning_service.prune.assert_called_once()


def test_session_orchestrator_passes_plan_to_trigger_replan_on_validation_failure(
    orchestrator,
    mock_fs,
    mock_plan_parser,
    mock_plan_validator,
    container,
):
    """
    SessionOrchestrator should pass the current plan object to trigger_replan
    when validation fails, so that pruned context can be harvested.
    """
    # Arrange
    from teddy_executor.core.domain.models import Plan

    mock_plan = register_mock(container, Plan)
    mock_plan.title = "Test Plan"
    mock_plan.rationale = "Test Rationale"
    mock_plan.actions = []
    mock_plan.source_doc = None
    mock_plan.is_session = True
    mock_plan.metadata = {}

    mock_plan_parser.parse.return_value = mock_plan

    # Mock validation errors
    error = MagicMock()
    error.message = "Invalid action"
    mock_plan_validator.validate.return_value = [error]

    mock_fs.path_exists.return_value = True  # is_session_mode
    mock_fs.read_file.return_value = "plan content"

    plan_path = "path/to/01/plan.md"

    # Act
    orchestrator.execute(plan_path=plan_path)

    # Assert
    orchestrator._lifecycle_manager.trigger_replan.assert_called_once_with(
        plan_path=plan_path,
        errors=["Invalid action"],
        original_plan_content="plan content",
        title="Test Plan",
        rationale="Test Rationale",
        failed_resources={},  # is_session=True → gather_failed_resources returns {} immediately
        validation_ast=ANY,
        original_actions=[],
        plan=mock_plan,  # This is what we are adding
        is_session=True,  # Added by bugfix: propagate is_session flag
    )


def test_session_orchestrator_harvests_context_in_interactive_mode(  # noqa: PLR0913
    orchestrator,
    mock_run_plan,
    mock_fs,
    mock_plan_parser,
    mock_plan_validator,
    container,
):
    """
    SessionOrchestrator should harvest pruned context into plan metadata
    even in interactive mode.
    """
    # Arrange
    from teddy_executor.core.domain.models import Plan

    mock_plan = register_mock(container, Plan)
    mock_plan.metadata = {}
    mock_plan.is_session = True

    # Setup execution mocks
    mock_plan_parser.parse.return_value = mock_plan
    mock_plan_validator.validate.return_value = []
    mock_fs.path_exists.return_value = True

    # Setup context with unselected items
    item_pruned = MagicMock()
    item_pruned.path = "pruned.txt"
    item_pruned.selected = False

    item_selected = MagicMock()
    item_selected.path = "selected.txt"
    item_selected.selected = True

    project_context = MagicMock()
    project_context.items = [item_pruned, item_selected]
    orchestrator._context_service.get_context.return_value = project_context

    # Ensure pruning service returns the context so harvesting sees our items
    orchestrator._pruning_service.prune.side_effect = lambda ctx, **kwargs: ctx

    # Act
    orchestrator.execute(plan_path="path/to/01/plan.md", interactive=True)

    # Assert
    assert mock_plan.metadata.get("pruned_context") == "pruned.txt"


class TestTeeGuard:
    """Tests for the Tee installation guard in SessionOrchestrator.execute()."""

    def test_orchestrator_skips_tee_when_lifecycle_active(  # noqa: PLR0913
        self,
        orchestrator,
        mock_run_plan,
        mock_fs,
        mock_plan_parser,
        mock_plan_validator,
        container,
        monkeypatch,
    ) -> None:
        """When lifecycle_manager.tee_active is True, orchestrator must not install Tee."""
        from unittest.mock import MagicMock
        from teddy_executor.core.domain.models import Plan
        from teddy_executor.core.domain.models.execution_report import (
            ExecutionReport,
            RunStatus,
            RunSummary,
        )
        from datetime import datetime, timezone

        mock_tee_class = MagicMock()
        monkeypatch.setattr(
            "teddy_executor.core.services.session_orchestrator._Tee",
            mock_tee_class,
        )

        # Ensure execution returns a report
        mock_run_plan.execute.return_value = ExecutionReport(
            run_summary=RunSummary(
                status=RunStatus.SUCCESS,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            ),
            plan_title="Test",
            rationale="Test",
        )

        # Set lifecycle_manager.tee_active to True
        orchestrator._lifecycle_manager.tee_active = True

        # Set up session mode
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = "plan content"

        mock_plan = register_mock(container, Plan)
        mock_plan.metadata = {}
        mock_plan.is_session = True
        mock_plan_parser.parse.return_value = mock_plan
        mock_plan_validator.validate.return_value = []

        # Mock context service
        orchestrator._context_service.get_context.return_value = MagicMock()
        orchestrator._pruning_service.prune.side_effect = lambda ctx, **kwargs: ctx

        plan_content = MarkdownPlanBuilder("Test").build()
        plan_path = "path/to/01/plan.md"

        orchestrator.execute(plan_content=plan_content, plan_path=plan_path)

        # _Tee must NOT be called since lifecycle_manager already installed it
        mock_tee_class.assert_not_called()

    def test_orchestrator_installs_tee_when_not_active(
        self,
        orchestrator,
        mock_run_plan,
        mock_fs,
        mock_plan_parser,
        mock_plan_validator,
        container,
        monkeypatch,
    ) -> None:
        """When lifecycle_manager.tee_active is False, orchestrator must install Tee."""
        from unittest.mock import MagicMock
        from teddy_executor.core.domain.models import Plan
        from teddy_executor.core.domain.models.execution_report import (
            ExecutionReport,
            RunStatus,
            RunSummary,
        )
        from datetime import datetime, timezone

        mock_tee_class = MagicMock()
        monkeypatch.setattr(
            "teddy_executor.core.services.session_orchestrator._Tee",
            mock_tee_class,
        )

        mock_run_plan.execute.return_value = ExecutionReport(
            run_summary=RunSummary(
                status=RunStatus.SUCCESS,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            ),
            plan_title="Test",
            rationale="Test",
        )

        # Ensure tee_active is False (default)
        orchestrator._lifecycle_manager.tee_active = False

        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = "plan content"

        mock_plan = register_mock(container, Plan)
        mock_plan.metadata = {}
        mock_plan.is_session = True
        mock_plan_parser.parse.return_value = mock_plan
        mock_plan_validator.validate.return_value = []

        orchestrator._context_service.get_context.return_value = MagicMock()
        orchestrator._pruning_service.prune.side_effect = lambda ctx, **kwargs: ctx

        plan_content = MarkdownPlanBuilder("Test").build()
        plan_path = "path/to/01/plan.md"

        orchestrator.execute(plan_content=plan_content, plan_path=plan_path)

        # _Tee must be called once (constructor call)
        mock_tee_class.assert_called_once()


class TestConsoleVisibilityHelpers:
    """Unit tests for console visibility helper functions (_print_initial_request, _print_header_bar, _print_user_message)."""

    @pytest.fixture(autouse=True)
    def _mock_typer(self, monkeypatch):
        """Mock typer.secho to capture calls."""
        self.secho_calls = []
        monkeypatch.setattr(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            self._fake_secho,
        )

    def _fake_secho(self, text, **kwargs):
        self.secho_calls.append((text, kwargs))

    # ------------------------------------------------------------------ #
    # _print_initial_request
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize(
        ("message", "is_session", "expected_calls"),
        [
            # Happy: session + non-empty message -> prints label + content (no trailing blank line)
            ("Hello", True, [("", {}), ("Initial Request:", {}), ("Hello", {})]),
            # Non-session: no output
            ("Hello", False, []),
            # Empty message: no output even if session
            ("", True, []),
            ("  ", True, []),
        ],
    )
    def test_print_initial_request(
        self, message, is_session, expected_calls, orchestrator
    ):
        """_print_initial_request should produce output only when is_session and message non-empty."""
        from teddy_executor.core.services.session_orchestrator import (
            _print_initial_request,
        )

        _print_initial_request(message, is_session)

        assert self.secho_calls == expected_calls

    # ------------------------------------------------------------------ #
    # _print_header_bar
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize(
        ("plan_title", "plan_metadata", "is_session", "expected_calls"),
        [
            # Happy: session, status with emoji -> prints emoji + title
            ("Refactor", {"Status": "SUCCESS 🟢"}, True, [("🟢 Refactor", {})]),
            # Non-session: no output
            ("Refactor", {"Status": "SUCCESS 🟢"}, False, []),
            # Missing emoji (no status) -> prints title alone
            ("Refactor", {}, True, [("Refactor", {})]),
            # Emoji in non-anchored metadata -> still falls back to first emoji
            ("Refactor", {"Status": "FAILED 🔴"}, True, [("🔴 Refactor", {})]),
            # Empty title + no emoji -> no output (parts list empty)
            ("", {}, True, []),
        ],
    )
    def test_print_header_bar(
        self, plan_title, plan_metadata, is_session, expected_calls
    ):
        """_print_header_bar should print emoji + title only when is_session=True."""
        from unittest.mock import MagicMock
        from teddy_executor.core.domain.models import Plan

        plan = MagicMock(spec=Plan)
        plan.title = plan_title
        plan.metadata = plan_metadata

        from teddy_executor.core.services.session_orchestrator import (
            _print_header_bar,
        )

        _print_header_bar(plan, is_session)

        assert self.secho_calls == expected_calls

    # ------------------------------------------------------------------ #
    # _print_user_message
    # ------------------------------------------------------------------ #

    @pytest.mark.parametrize(
        ("message", "is_session", "expected_calls"),
        [
            # Happy: session + non-empty -> blank line, label, content
            (
                "User feedback",
                True,
                [
                    ("", {}),
                    ("User Message:", {}),
                    ("User feedback", {}),
                ],
            ),
            # Non-session: no output
            ("User feedback", False, []),
            # Empty message: no output even if session
            ("", True, []),
            ("  ", True, []),
        ],
    )
    def test_print_user_message(self, message, is_session, expected_calls):
        """_print_user_message should produce output only when is_session and message non-empty."""
        from teddy_executor.core.services.session_orchestrator import (
            _print_user_message,
        )

        _print_user_message(message, is_session)

        assert self.secho_calls == expected_calls


class TestConsoleVisibilityWiring:
    """Tests that console visibility helpers are called by SessionOrchestrator.execute()."""

    @pytest.fixture(autouse=True)
    def _patch_helpers(self, monkeypatch):
        """Patch all three helper functions with tracking mocks."""
        self.print_initial_request_calls = []
        self.print_header_bar_calls = []
        self.print_user_message_calls = []

        def _track_print_initial_request(message, is_session, **kwargs):
            self.print_initial_request_calls.append((message, is_session))

        def _track_print_header_bar(plan, is_session, **kwargs):
            self.print_header_bar_calls.append((plan, is_session))

        def _track_print_user_message(message, is_session, **kwargs):
            self.print_user_message_calls.append((message, is_session))

        monkeypatch.setattr(
            "teddy_executor.core.services.session_orchestrator._print_initial_request",
            _track_print_initial_request,
        )
        monkeypatch.setattr(
            "teddy_executor.core.services.session_orchestrator._print_header_bar",
            _track_print_header_bar,
        )
        monkeypatch.setattr(
            "teddy_executor.core.services.session_orchestrator._print_user_message",
            _track_print_user_message,
        )

    @pytest.mark.parametrize(
        ("message", "is_session", "expected_calls"),
        [
            # Session with message: all three helpers should be called
            (
                "User message",
                True,
                ("User message", "User message", "User message"),
            ),
            # Session with empty message: no helpers should be called (early return on empty message)
            (
                "",
                True,
                (None, None, None),
            ),
            # Non-session: no helpers should be called
            (
                "User message",
                False,
                (None, None, None),
            ),
        ],
        ids=["session_with_message", "session_empty_message", "non_session"],
    )
    def test_helpers_called_during_execute(
        self,
        message,
        is_session,
        expected_calls,
        orchestrator,
        mock_run_plan,
        mock_fs,
        mock_plan_parser,
        mock_plan_validator,
        container,
    ):
        """Wiring: helpers should be called with the expected arguments during execute()."""
        from teddy_executor.core.domain.models import Plan
        from unittest.mock import MagicMock

        # Mock plan
        mock_plan = MagicMock(spec=Plan)
        mock_plan.title = "Test Plan"
        mock_plan.metadata = {
            "Status": "SUCCESS 🟢",
            "user_request": message if message and message.strip() else "",
        }
        mock_plan.is_session = is_session

        # Setup mocks for execution flow
        mock_plan_parser.parse.return_value = mock_plan
        mock_plan_validator.validate.return_value = []
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = "plan content"

        # Context service must return something for pruning/harvesting
        orchestrator._context_service.get_context.return_value = MagicMock()
        orchestrator._pruning_service.prune.side_effect = lambda ctx, **kwargs: ctx

        # Ensure execution returns a report (session termination check passes)
        from teddy_executor.core.domain.models.execution_report import (
            ExecutionReport,
            RunStatus,
            RunSummary,
        )
        from datetime import datetime, timezone

        mock_run_plan.execute.return_value = ExecutionReport(
            run_summary=RunSummary(
                status=RunStatus.SUCCESS,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            ),
            plan_title="Test Plan",
            rationale="Test Rationale",
        )

        # Mock lifecycle manager's finalize_turn to prevent side-effects
        orchestrator._lifecycle_manager.finalize_turn.return_value = None

        # Only set plan_path for session mode; non-session uses no path so is_session is False
        plan_path = "path/to/01/plan.md" if is_session else None

        # Act
        orchestrator.execute(
            plan_content="plan content",
            plan_path=plan_path,
            message=message,
            interactive=True,
        )

        # _print_initial_request: no longer called from orchestrator (lifecycle manager handles it)
        assert len(self.print_initial_request_calls) == 0

        # _print_header_bar: called only when the flow reaches that point.
        # Early return on empty message prevents it; non-session mode also prevents it.
        if is_session and message and message.strip():
            assert len(self.print_header_bar_calls) == 1
            actual_plan, actual_is_session = self.print_header_bar_calls[0]
            assert actual_is_session is True
        else:
            assert len(self.print_header_bar_calls) == 0

        # _print_user_message: called only if is_session and message non-empty
        if is_session and message.strip():
            assert len(self.print_user_message_calls) == 1
            actual_message, actual_is_session = self.print_user_message_calls[0]
            assert actual_message == message
            assert actual_is_session is True
        else:
            assert len(self.print_user_message_calls) == 0
