"""Regression: auto-pruning MUST run on the primary session path.

Every normal interactive/pipeline session turn hands
``SessionOrchestrator.execute`` a planning-gathered ``project_context``. A
refactor had relocated the sole ``SessionPruningService.prune()`` call into the
fallback-only re-gather helper (which runs only when ``project_context is None``),
so the primary path silently skipped ALL pruning heuristics and ``turn.context``
grew without bound — sessions ballooned far past ``turn_context_threshold``.

This test drives the primary path with an oversized Turn-scope context and
asserts the configured token budget actually deselects the largest file. It
fails against the pre-fix code (pruning is skipped) and passes once ``prune()``
runs on the primary path.
"""

from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest

from teddy_executor.core.domain.models import ContextItem, ProjectContext
from teddy_executor.core.domain.models.execution_report import RunStatus
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from teddy_executor.core.services.session_replanner import SessionReplanner

TURN_CONTEXT_THRESHOLD = 1000


class RecordingExecutionOrchestrator:
    """In-memory fake recording the ``project_context`` handed to execution."""

    def __init__(self, report):
        self._report = report
        self.contexts = []

    def execute(self, **kwargs):
        self.contexts.append(kwargs.get("project_context"))
        return self._report


class PassingPlanValidator:
    """In-memory fake that reports a plan as valid (no errors)."""

    def validate(self, *args, **kwargs):
        return []


class FakeLifecycleManager:
    """Minimal fake exposing only the surface ``SessionOrchestrator`` touches."""

    tee_active = True  # skips the orchestrator's Tee installation branch

    def finalize_turn(self, plan_path, report, is_validation_failure=False, plan=None):
        return "session/03"


@pytest.fixture
def config_service():
    service = create_autospec(IConfigService, instance=True)
    service.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.turn_context_threshold": TURN_CONTEXT_THRESHOLD,
        "auto_pruning.prune_failure_history": True,
        "auto_pruning.prune_validation_failures": True,
    }.get(key, default)
    return service


@pytest.fixture
def file_system_manager():
    fs = create_autospec(IFileSystemManager, instance=True)
    fs.path_exists.return_value = True
    return fs


@pytest.fixture
def execution_orchestrator():
    return RecordingExecutionOrchestrator(
        SimpleNamespace(
            run_summary=SimpleNamespace(status=RunStatus.SUCCESS),
            action_logs=[],
        )
    )


@pytest.fixture
def orchestrator(config_service, file_system_manager, execution_orchestrator):
    pruning_service = SessionPruningService(
        config_service=config_service,
        file_system_manager=file_system_manager,
    )
    prompt_manager = create_autospec(IPromptManager, instance=True)
    prompt_manager.fetch_system_prompt.return_value = "system prompt"
    llm_client = create_autospec(ILlmClient, instance=True)
    llm_client.get_text_token_count.return_value = 100
    llm_client.get_context_window.return_value = 200000

    return SessionOrchestrator(
        execution_orchestrator=execution_orchestrator,
        session_service=create_autospec(ISessionManager, instance=True),
        file_system_manager=file_system_manager,
        plan_validator=PassingPlanValidator(),
        plan_parser=create_autospec(IPlanParser, instance=True),
        user_interactor=create_autospec(IUserInteractor, instance=True),
        lifecycle_manager=FakeLifecycleManager(),
        replanner=create_autospec(SessionReplanner, instance=True),
        context_service=create_autospec(IGetContextUseCase, instance=True),
        config_service=config_service,
        llm_client=llm_client,
        prompt_manager=prompt_manager,
        pruning_service=pruning_service,
    )


def test_primary_path_prunes_oversized_turn_scope_context(
    orchestrator, execution_orchestrator
):
    """A planning-gathered context MUST be pruned against the Turn-scope budget."""
    plan = Plan(
        title="Primary path pruning regression",
        rationale="Pruning was skipped whenever a project_context was provided.",
        actions=[ActionData(type="EXECUTE", params={})],
        metadata={"Agent": "Developer"},
        source_doc=None,
    )
    orchestrator._plan_parser.parse.return_value = plan
    oversized_context = ProjectContext(
        header="",
        content="",
        items=[
            ContextItem(path="big1.py", token_count=800, git_status="", scope="Turn"),
            ContextItem(path="big2.py", token_count=800, git_status="", scope="Turn"),
        ],
    )

    orchestrator.execute(
        plan=plan,
        plan_path="session/02/plan.md",
        project_context=oversized_context,
    )

    assert execution_orchestrator.contexts, "execution was never invoked"
    passed_context = execution_orchestrator.contexts[0]
    pruned_paths = [item.path for item in passed_context.items if not item.selected]

    assert pruned_paths, (
        "The primary session path (project_context provided) must run auto-pruning: "
        "an oversized Turn-scope context (1600 tokens > 1000 threshold) was passed "
        "through unpruned."
    )
    assert "big1.py" in pruned_paths
    assert all(
        item.auto_prune_reason == "Pruned to fit context budget"
        for item in passed_context.items
        if not item.selected
    )
