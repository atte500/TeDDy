from textual.app import App, ComposeResult
from textual.widgets import Tree, Footer, Header, Static
from textual.containers import Vertical

class SectionJumpTree(Tree):
    def action_jump_next(self):
        """Jump to the next major section."""
        target_found = False
        # Sections are top-level children of the hidden root
        for child in self.root.children:
            if child.data in ["RATIONALE_ROOT", "ACTION_PLAN_ROOT"]:
                # If we are currently in or below Rationale, jump to Action Plan
                if self.cursor_node.data == "RATIONALE_ROOT" or self.cursor_node in self.root.children[0].children:
                     if child.data == "ACTION_PLAN_ROOT":
                         self.move_cursor(child)
                         return

    def action_jump_prev(self):
        """Jump to the previous major section."""
        for child in self.root.children:
            if child.data == "RATIONALE_ROOT":
                self.move_cursor(child)
                return

class SpikeApp(App):
    BINDINGS = [
        ("ctrl+down", "jump_next", "Next Section"),
        ("ctrl+up", "jump_prev", "Prev Section"),
        ("q", "quit", "Quit")
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield SectionJumpTree("Hidden Root")
        yield Footer()

    def on_mount(self):
        tree = self.query_one(SectionJumpTree)
        tree.show_root = False

        rat = tree.root.add("Rationale", data="RATIONALE_ROOT", expand=True)
        rat.add_leaf("Sub 1")
        rat.add_leaf("Sub 2")

        act = tree.root.add("Action Plan", data="ACTION_PLAN_ROOT", expand=True)
        act.add_leaf("Action 1")
        act.add_leaf("Action 2")

        tree.move_cursor(rat)
        tree.focus()

    def action_jump_next(self):
        self.query_one(SectionJumpTree).action_jump_next()

    def action_jump_prev(self):
        self.query_one(SectionJumpTree).action_jump_prev()

if __name__ == "__main__":
    app = SpikeApp()
    app.run()
