"""Interface: the plan reviewer accepts an optional configuration service.

The handle is optional (defaults to None) so every existing construction site
stays valid. ``ReviewerApp`` exposes it publicly so the plan viewer can read
``plan.max_lines``, and ``TextualPlanReviewer`` threads it into ``ReviewerApp``.
"""

from teddy_executor.adapters.inbound.textual_plan_reviewer import (
    ReviewerApp,
    TextualPlanReviewer,
)
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.outbound import IConfigService, IFileSystemManager
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from tests.harness.setup.mocking import register_mock


def _plan() -> Plan:
    return Plan(
        title="T",
        rationale="R",
        actions=[ActionData(type="READ", params={"path": "x"})],
    )


def test_reviewer_app_defaults_config_service_to_none(container):
    app = ReviewerApp(
        plan=_plan(),
        system_env=register_mock(container, ISystemEnvironment),
        console_tooling=register_mock(container, ConsoleToolingHelper),
        action_dispatcher=register_mock(container, ActionDispatcher),
    )

    assert app.config_service is None


def test_reviewer_app_stores_the_injected_config_service(container):
    config_service = register_mock(container, IConfigService)

    app = ReviewerApp(
        plan=_plan(),
        system_env=register_mock(container, ISystemEnvironment),
        console_tooling=register_mock(container, ConsoleToolingHelper),
        action_dispatcher=register_mock(container, ActionDispatcher),
        config_service=config_service,
    )

    assert app.config_service is config_service


def test_textual_plan_reviewer_defaults_config_service_to_none(container):
    reviewer = TextualPlanReviewer(
        system_env=register_mock(container, ISystemEnvironment),
        file_system=register_mock(container, IFileSystemManager),
        console_tooling=register_mock(container, ConsoleToolingHelper),
        action_dispatcher=register_mock(container, ActionDispatcher),
    )

    assert reviewer._config_service is None


def test_textual_plan_reviewer_stores_the_injected_config_service(container):
    config_service = register_mock(container, IConfigService)

    reviewer = TextualPlanReviewer(
        system_env=register_mock(container, ISystemEnvironment),
        file_system=register_mock(container, IFileSystemManager),
        console_tooling=register_mock(container, ConsoleToolingHelper),
        action_dispatcher=register_mock(container, ActionDispatcher),
        config_service=config_service,
    )

    assert reviewer._config_service is config_service
