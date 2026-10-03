import yaml
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.adapters.inbound.textual_plan_reviewer import TextualPlanReviewer
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


def test_container_ignores_stale_console_config(fs):
    # Arrange: A stale ui_mode: console key lingers in a user's config
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=yaml.dump({"ui_mode": "console"}))

    container = create_container()

    # Act
    reviewer = container.resolve(IPlanReviewer)

    # Assert: the console-selection branch is gone, so the stale key is ignored
    assert isinstance(reviewer, TextualPlanReviewer)
