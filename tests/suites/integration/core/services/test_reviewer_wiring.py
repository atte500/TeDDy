import yaml
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.ports.outbound import IConfigService, ISessionManager
from teddy_executor.adapters.inbound.textual_plan_reviewer import TextualPlanReviewer
from teddy_executor.adapters.outbound.local_agent_catalog import LocalAgentCatalog
from teddy_executor.container import create_container


def test_container_resolves_textual_reviewer(fs):
    # Arrange: No ui_mode configuration (TUI is the sole reviewer)
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents="{}")

    # We create a fresh container to ensure config is read during registration
    container = create_container()

    # Act
    reviewer = container.resolve(IPlanReviewer)

    # Assert
    assert isinstance(reviewer, TextualPlanReviewer)
    assert isinstance(reviewer._config_service, IConfigService)


def test_container_ignores_stale_console_config(fs):
    # Arrange: A stale ui_mode: console key lingers in a user's config
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=yaml.dump({"ui_mode": "console"}))

    container = create_container()

    # Act
    reviewer = container.resolve(IPlanReviewer)

    # Assert: the console-selection branch is gone, so the stale key is ignored
    assert isinstance(reviewer, TextualPlanReviewer)


def test_container_hands_the_reviewer_its_agent_switching_handles(fs):
    """The reviewer the container builds can actually switch persona.

    Both handles are optional on ``TextualPlanReviewer`` because many call sites
    construct the app directly, so the composition root is the only place that
    supplies them in production. Without these two resolutions the shipped
    reviewer reports "Agent switching is unavailable in this reviewer." even
    though the picker, the roster adapter, and the persistence primitive exist.

    The catalog is asserted by type rather than identity: the binding is
    transient, so a second ``resolve`` returns a different instance, and the
    adapter is never invoked here, so its workspace scan never runs.
    """
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents="{}")

    container = create_container()

    reviewer = container.resolve(IPlanReviewer)

    assert isinstance(reviewer, TextualPlanReviewer)
    assert isinstance(reviewer._agent_catalog, LocalAgentCatalog)
    assert isinstance(reviewer._session_manager, ISessionManager)
