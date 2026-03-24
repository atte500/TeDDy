import yaml
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.adapters.inbound.textual_plan_reviewer import TextualPlanReviewer
from teddy_executor.adapters.inbound.console_plan_reviewer import ConsolePlanReviewer
from teddy_executor.container import create_container


def test_container_resolves_textual_reviewer_by_default(fs):
    # Arrange: No config or default config
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents="{}")

    # We create a fresh container to ensure config is read during registration
    container = create_container()

    # Act
    reviewer = container.resolve(IPlanReviewer)

    # Assert
    assert isinstance(reviewer, TextualPlanReviewer)


def test_container_resolves_console_reviewer_when_configured(fs):
    # Arrange: Config set to console
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=yaml.dump({"ui_mode": "console"}))

    container = create_container()

    # Act
    reviewer = container.resolve(IPlanReviewer)

    # Assert
    assert isinstance(reviewer, ConsolePlanReviewer)


def test_container_resolves_textual_reviewer_when_configured(fs):
    # Arrange: Config set to tui
    fs.create_dir(".teddy")
    fs.create_file(".teddy/config.yaml", contents=yaml.dump({"ui_mode": "tui"}))

    container = create_container()

    # Act
    reviewer = container.resolve(IPlanReviewer)

    # Assert
    assert isinstance(reviewer, TextualPlanReviewer)
