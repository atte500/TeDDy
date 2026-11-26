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
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.domain.models.project_context import (
    ContextItem,
    ProjectContext,
)

from tests.harness.drivers.tui_driver import TuiDriver
from tests.harness.setup.reviewer_context_scenarios import (
    SESSION_ITEM_PATH,
    SESSION_ROOT,
    ReviewerContextShape,
    reviewer_project_context,
)


class TreeTestApp(App):
    def compose(self) -> ComposeResult:
        yield ActionTree("Root", id="tree")


@pytest.mark.anyio
async def test_jump_to_section_moves_cursor():
    app = TreeTestApp()
    async with app.run_test():
        tree = app.query_one(ActionTree)
        tree.show_root = False

        # Setup: Add nodes similar to production logic
        rat = tree.root.add("Rationale", data=ActionTree.RATIONALE_ROOT)
        act = tree.root.add("Action Plan", data=ActionTree.ACTION_PLAN_ROOT)

        # Initial state
        tree.move_cursor(rat)
        assert tree.cursor_node == rat

        # Act: Jump to Action Plan
        tree.jump_to_section(ActionTree.ACTION_PLAN_ROOT)

        # Assert: Cursor should have moved
        assert tree.cursor_node == act

        # Act: Jump back to Rationale
        tree.jump_to_section(ActionTree.RATIONALE_ROOT)
        assert tree.cursor_node == rat


@pytest.mark.anyio
async def test_jump_to_section_handles_missing_target():
    app = TreeTestApp()
    async with app.run_test():
        tree = app.query_one(ActionTree)
        tree.show_root = False
        rat = tree.root.add("Rationale", data=ActionTree.RATIONALE_ROOT)
        tree.move_cursor(rat)

        # Act: Jump to non-existent section should not crash or move cursor
        tree.jump_to_section("NON_EXISTENT")
        assert tree.cursor_node == rat


def _plan() -> Plan:
    return Plan(
        title="Navigation",
        rationale="### Summary\nDrive the section tree.",
        actions=[ActionData(type="READ", params={"resource": "README.md"})],
    )


def _driver(mock_env, mock_fs, shape: ReviewerContextShape) -> TuiDriver:
    return TuiDriver(
        plan=_plan(),
        system_env=mock_env,
        file_system=mock_fs,
        project_context=reviewer_project_context(shape),
    )


def _payloads(tree) -> list[str]:
    """Return the payload of every section the walk reaches, in order."""
    return [node.data for node in section_sequence(tree)]


def _first_node(tree, matches):
    """Return the first node whose payload satisfies ``matches``."""
    stack = [tree.root]
    while stack:
        node = stack.pop()
        if matches(node.data):
            return node
        stack.extend(reversed(node.children))
    raise AssertionError("no node in the tree matched the search")


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
        plan=_plan(),
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
        row = _first_node(driver.tree(pilot), _is_session_file_row)
        assert containing_section(row).data == SESSION_LABEL


@pytest.mark.anyio
async def test_containing_section_resolves_the_agent_row_to_the_system_group(
    mock_env, mock_fs
):
    driver = _driver(mock_env, mock_fs, "populated")

    async with driver.interaction() as pilot:
        row = _first_node(driver.tree(pilot), _is_agent_row)
        assert containing_section(row).data == SYSTEM_LABEL


@pytest.mark.anyio
async def test_containing_section_finds_nothing_above_the_invisible_root(
    mock_env, mock_fs
):
    driver = _driver(mock_env, mock_fs, "populated")

    async with driver.interaction() as pilot:
        assert containing_section(driver.tree(pilot).root) is None
