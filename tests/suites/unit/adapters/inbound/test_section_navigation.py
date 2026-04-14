import pytest
from textual.app import App, ComposeResult
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import ActionTree


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
