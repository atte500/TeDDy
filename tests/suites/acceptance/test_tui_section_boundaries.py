"""Acceptance coverage for boundary-aware section navigation.

Alt+Down walks the sections the tree actually built, so the context subsections
are reachable, and the walk stops at both ends instead of wrapping: the tree
scrolls to its last row at the bottom and back to its first row at the top.
"""

import pytest

from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    ACTION_PLAN_ROOT,
    CONTEXT_ROOT,
    RATIONALE_ROOT,
    SESSION_LABEL,
    SYSTEM_LABEL,
    TURN_LABEL,
)
from tests.harness.drivers.tui_driver import TuiDriver
from tests.harness.setup.reviewer_context_scenarios import (
    SESSION_ITEM_PATH,
    ReviewerContextShape,
    reviewer_plan,
    reviewer_project_context,
)

# Enough actions that the action plan cannot fit the default 80x24 viewport,
# so a scroll assertion observes a real scroll instead of a no-op.
OVERFLOWING_ACTION_COUNT = 40

SECTION_WALK = [
    CONTEXT_ROOT,
    SYSTEM_LABEL,
    SESSION_LABEL,
    TURN_LABEL,
    RATIONALE_ROOT,
    ACTION_PLAN_ROOT,
]


def _driver(
    mock_env, mock_fs, shape: ReviewerContextShape, action_count: int = 1
) -> TuiDriver:
    return TuiDriver(
        plan=reviewer_plan(action_count),
        system_env=mock_env,
        file_system=mock_fs,
        project_context=reviewer_project_context(shape),
    )


async def _press(pilot, key: str) -> None:
    await pilot.press(key)
    await pilot.pause()


@pytest.mark.anyio
async def test_alt_down_visits_every_context_group_before_the_plan(mock_env, mock_fs):
    driver = _driver(mock_env, mock_fs, "history_less")

    async with driver.interaction() as pilot:
        context_root = driver.find_node(pilot, lambda data: data == CONTEXT_ROOT)
        assert context_root.is_expanded is False

        visited = [driver.cursor_data(pilot)]
        for _ in range(len(SECTION_WALK) - 1):
            await _press(pilot, "alt+down")
            visited.append(driver.cursor_data(pilot))

        assert visited == SECTION_WALK
        assert context_root.is_expanded is True


@pytest.mark.anyio
async def test_alt_down_at_the_last_section_scrolls_instead_of_wrapping(
    mock_env, mock_fs
):
    driver = _driver(mock_env, mock_fs, "history_less", OVERFLOWING_ACTION_COUNT)

    async with driver.interaction() as pilot:
        tree = driver.tree(pilot)
        for _ in range(len(SECTION_WALK) - 1):
            await _press(pilot, "alt+down")
        assert driver.cursor_data(pilot) == ACTION_PLAN_ROOT
        assert tree.max_scroll_y > 0, "the plan must overflow the tree viewport"

        await _press(pilot, "alt+down")

        assert driver.cursor_data(pilot) == ACTION_PLAN_ROOT
        assert tree.scroll_y == tree.max_scroll_y


@pytest.mark.anyio
async def test_alt_up_at_the_first_section_scrolls_instead_of_wrapping(
    mock_env, mock_fs
):
    driver = _driver(mock_env, mock_fs, "history_less", OVERFLOWING_ACTION_COUNT)

    async with driver.interaction() as pilot:
        tree = driver.tree(pilot)
        assert driver.cursor_data(pilot) == CONTEXT_ROOT

        tree.scroll_end(animate=False)
        await pilot.pause()
        assert tree.scroll_y > 0, "the plan must overflow the tree viewport"

        await _press(pilot, "alt+up")

        assert driver.cursor_data(pilot) == CONTEXT_ROOT
        assert tree.scroll_y == 0


@pytest.mark.anyio
async def test_alt_down_from_a_file_row_advances_past_its_group(mock_env, mock_fs):
    driver = _driver(mock_env, mock_fs, "history_less")

    async with driver.interaction() as pilot:
        tree = driver.tree(pilot)
        driver.find_node(pilot, lambda data: data == CONTEXT_ROOT).expand()
        await pilot.pause()

        row = driver.find_node(
            pilot, lambda data: getattr(data, "path", None) == SESSION_ITEM_PATH
        )
        tree.move_cursor(row)
        await pilot.pause()

        await _press(pilot, "alt+down")

        assert driver.cursor_data(pilot) == TURN_LABEL
