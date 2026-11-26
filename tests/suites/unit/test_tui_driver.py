"""Contract tests for the TUI reviewer driver's harness surface.

The driver is the only way a reviewer test mounts the app, observes the tree
while it runs, and injects the context-panel shape a scenario needs. These
tests pin that surface: each canonical panel shape reaches the tree that the
production mount builds, and the interaction hook hands back a focused tree so
key presses reach the section bindings.
"""

import pytest

from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    ACTION_PLAN_ROOT,
    CONTEXT_ROOT,
    HISTORY_LABEL,
    RATIONALE_ROOT,
    SESSION_LABEL,
    SYSTEM_LABEL,
    TURN_LABEL,
)
from tests.harness.drivers.tui_driver import TuiDriver
from tests.harness.setup.reviewer_context_scenarios import (
    ReviewerContextShape,
    reviewer_plan,
    reviewer_project_context,
)


def _driver(mock_env, mock_fs, shape: ReviewerContextShape) -> TuiDriver:
    return TuiDriver(
        plan=reviewer_plan(),
        system_env=mock_env,
        file_system=mock_fs,
        project_context=reviewer_project_context(shape),
    )


def _group_sentinels(tree) -> list[str]:
    """Return the context panel's group headers in render order."""
    root_children = tree.root.children
    assert root_children[0].data == CONTEXT_ROOT
    return [
        child.data for child in root_children[0].children if isinstance(child.data, str)
    ]


@pytest.mark.anyio
async def test_populated_panel_renders_every_context_group(mock_env, mock_fs):
    driver = _driver(mock_env, mock_fs, "populated")

    async with driver.interaction() as pilot:
        assert driver.cursor_data(pilot) == CONTEXT_ROOT
        assert _group_sentinels(driver.tree(pilot)) == [
            SYSTEM_LABEL,
            SESSION_LABEL,
            TURN_LABEL,
            HISTORY_LABEL,
        ]


@pytest.mark.anyio
async def test_history_less_panel_omits_the_history_group(mock_env, mock_fs):
    driver = _driver(mock_env, mock_fs, "history_less")

    async with driver.interaction() as pilot:
        assert _group_sentinels(driver.tree(pilot)) == [
            SYSTEM_LABEL,
            SESSION_LABEL,
            TURN_LABEL,
        ]


@pytest.mark.anyio
async def test_context_less_panel_starts_on_the_rationale_root(mock_env, mock_fs):
    driver = _driver(mock_env, mock_fs, "none")

    async with driver.interaction() as pilot:
        tree = driver.tree(pilot)
        assert [child.data for child in tree.root.children] == [
            RATIONALE_ROOT,
            ACTION_PLAN_ROOT,
        ]
        assert driver.cursor_data(pilot) == RATIONALE_ROOT


@pytest.mark.anyio
async def test_interaction_hands_back_a_focused_tree(mock_env, mock_fs):
    driver = _driver(mock_env, mock_fs, "none")

    async with driver.interaction() as pilot:
        assert driver.tree(pilot).has_focus
