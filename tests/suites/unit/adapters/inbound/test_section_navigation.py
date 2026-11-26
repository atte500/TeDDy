import pytest
from textual.app import App, ComposeResult

from teddy_executor.adapters.inbound.textual_plan_reviewer_helpers import (
    containing_section,
    section_sequence,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    ACTION_PLAN_ROOT,
    CONTEXT_ROOT,
    HISTORY_LABEL,
    RATIONALE_ROOT,
    SESSION_LABEL,
    SYSTEM_LABEL,
    TURN_LABEL,
)
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ActionTree
from teddy_executor.core.domain.models.project_context import (
    ContextItem,
    ProjectContext,
)

from tests.harness.drivers.tui_driver import TuiDriver
from tests.harness.setup.reviewer_context_scenarios import (
    SESSION_ITEM_PATH,
    SESSION_ROOT,
    ReviewerContextShape,
    reviewer_plan,
    reviewer_project_context,
)


class TreeTestApp(App):
    def compose(self) -> ComposeResult:
        yield ActionTree("Root", id="tree")


@pytest.mark.anyio
async def test_jump_to_node_moves_the_cursor_between_visible_sections():
    app = TreeTestApp()
    async with app.run_test():
        tree = app.query_one(ActionTree)
        tree.show_root = False
        rationale = tree.root.add("Rationale", data=RATIONALE_ROOT)
        action_plan = tree.root.add("Action Plan", data=ACTION_PLAN_ROOT)
        tree.move_cursor(rationale)
        assert tree.cursor_node == rationale

        tree.jump_to_node(action_plan)
        assert tree.cursor_node == action_plan

        tree.jump_to_node(rationale)
        assert tree.cursor_node == rationale


@pytest.mark.anyio
async def test_jump_to_node_reveals_a_collapsed_subsection():
    app = TreeTestApp()
    async with app.run_test() as pilot:
        tree = app.query_one(ActionTree)
        tree.show_root = False
        session = tree.root.add("Session", data=SESSION_LABEL)
        row = session.add_leaf("  src/core.py", data="ROW")
        tree.move_cursor(session)
        await pilot.pause()
        assert session.is_expanded is False

        tree.jump_to_node(row)
        await pilot.pause()

        assert session.is_expanded is True
        assert tree.cursor_node == row


def _driver(mock_env, mock_fs, shape: ReviewerContextShape) -> TuiDriver:
    return TuiDriver(
        plan=reviewer_plan(),
        system_env=mock_env,
        file_system=mock_fs,
        project_context=reviewer_project_context(shape),
    )


def _payloads(tree) -> list[str]:
    """Return the payload of every section the walk reaches, in order."""
    return [node.data for node in section_sequence(tree)]


def _is_session_file_row(data) -> bool:
    """Report whether a node payload is the Session group's file row."""
    return getattr(data, "path", None) == SESSION_ITEM_PATH


def _is_agent_row(data) -> bool:
    """Report whether a node payload is the Context panel's agent leaf."""
    return isinstance(data, dict) and data.get("type") == "SYSTEM_PROMPT"


@pytest.mark.anyio
async def test_walk_reaches_every_context_group_before_the_plan(mock_env, mock_fs):
    driver = _driver(mock_env, mock_fs, "populated")

    async with driver.interaction() as pilot:
        assert _payloads(driver.tree(pilot)) == [
            CONTEXT_ROOT,
            SYSTEM_LABEL,
            SESSION_LABEL,
            TURN_LABEL,
            HISTORY_LABEL,
            RATIONALE_ROOT,
            ACTION_PLAN_ROOT,
        ]


@pytest.mark.anyio
async def test_walk_skips_a_history_group_the_panel_did_not_build(mock_env, mock_fs):
    driver = _driver(mock_env, mock_fs, "history_less")

    async with driver.interaction() as pilot:
        assert _payloads(driver.tree(pilot)) == [
            CONTEXT_ROOT,
            SYSTEM_LABEL,
            SESSION_LABEL,
            TURN_LABEL,
            RATIONALE_ROOT,
            ACTION_PLAN_ROOT,
        ]


@pytest.mark.anyio
async def test_walk_without_a_context_panel_starts_at_the_rationale(mock_env, mock_fs):
    driver = _driver(mock_env, mock_fs, "none")

    async with driver.interaction() as pilot:
        assert _payloads(driver.tree(pilot)) == [RATIONALE_ROOT, ACTION_PLAN_ROOT]


@pytest.mark.anyio
async def test_an_empty_scope_group_is_one_stop_not_two(mock_env, mock_fs):
    context = ProjectContext(
        header="H",
        content="C",
        items=[
            ContextItem(
                path=SESSION_ITEM_PATH,
                token_count=1200,
                git_status="M",
                scope="Session",
            )
        ],
        agent_name="Developer",
        content_tokens=1200,
        session_root=SESSION_ROOT,
    )
    driver = TuiDriver(
        plan=reviewer_plan(),
        system_env=mock_env,
        file_system=mock_fs,
        project_context=context,
    )

    async with driver.interaction() as pilot:
        assert _payloads(driver.tree(pilot)) == [
            CONTEXT_ROOT,
            SYSTEM_LABEL,
            SESSION_LABEL,
            TURN_LABEL,
            RATIONALE_ROOT,
            ACTION_PLAN_ROOT,
        ]


@pytest.mark.anyio
async def test_containing_section_resolves_a_file_row_to_its_group(mock_env, mock_fs):
    driver = _driver(mock_env, mock_fs, "populated")

    async with driver.interaction() as pilot:
        row = driver.find_node(pilot, _is_session_file_row)
        assert containing_section(row).data == SESSION_LABEL


@pytest.mark.anyio
async def test_containing_section_resolves_the_agent_row_to_the_system_group(
    mock_env, mock_fs
):
    driver = _driver(mock_env, mock_fs, "populated")

    async with driver.interaction() as pilot:
        row = driver.find_node(pilot, _is_agent_row)
        assert containing_section(row).data == SYSTEM_LABEL


@pytest.mark.anyio
async def test_containing_section_finds_nothing_above_the_invisible_root(
    mock_env, mock_fs
):
    driver = _driver(mock_env, mock_fs, "populated")

    async with driver.interaction() as pilot:
        assert containing_section(driver.tree(pilot).root) is None
