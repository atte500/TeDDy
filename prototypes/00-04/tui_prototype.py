from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Label
from textual.containers import Vertical
from dataclasses import dataclass

@dataclass
class ContextItem:
    path: str
    token_count: int
    source_scope: str
    git_status: str
    selected: bool = True
    is_auto_pruned: bool = False

class ContextManagementView(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("[bold]Session Context Management[/]")
        yield Label("Toggle files to include/exclude from the next turn.")
        yield DataTable(id="context-table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("S", "Path", "Tokens", "Status", "Scope")
        table.cursor_type = "row"
        
        # Sample Data
        self.items = [
            ContextItem("src/core.py", 1200, "Session", "  "),
            ContextItem("src/utils.py", 450, "Session", " M"),
            ContextItem("docs/plan.md", 300, "Turn", "??"),
            ContextItem("tests/report.md", 1500, "Turn", "  ", selected=False, is_auto_pruned=True),
            ContextItem("src/heavy_logic.py", 15000, "Turn", " M", selected=False, is_auto_pruned=True),
        ]
        
        for i, item in enumerate(self.items):
            checkbox = " [x] " if item.selected else " [ ] "
            # Use styling for auto-pruned items
            path_display = item.path
            if item.is_auto_pruned:
                path_display = f"[yellow]{item.path}[/]"
            
            table.add_row(
                checkbox,
                path_display,
                str(item.token_count),
                f"({item.git_status})",
                item.source_scope,
                key=str(i)
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        idx = int(event.row_key.value)
        item = self.items[idx]
        
        # Session items are un-prunable (business rule)
        if item.source_scope.lower() == "session":
            return

        item.selected = not item.selected
        checkbox = " [x] " if item.selected else " [ ] "
        
        table = self.query_one(DataTable)
        table.update_cell(event.row_key, table.columns[0].key, checkbox)

from textual.containers import Horizontal, Vertical
from textual.widgets import ContentSwitcher, Tree

TUI_CSS = """
#main-container {
    layout: horizontal;
    height: 1fr;
}
#left-pane {
    width: 65%;
}
#right-pane {
    width: 35%;
    border-left: vkey $foreground 15%;
    padding: 0;
    background: $surface;
}
ContextManagementView {
    padding: 1 2;
}
DataTable {
    height: 1fr;
    margin-top: 1;
}
"""

class ShowcaseApp(App):
    CSS = TUI_CSS
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            tree = Tree("Plan", id="left-pane")
            tree.root.expand()
            tree.root.add("Rationale", expand=True)
            act_root = tree.root.add("Action Plan", expand=True)
            act_root.add_leaf("CREATE src/main.py")
            # The new target node
            tree.root.add_leaf("[bold]Session Context[/]", data="context_node")
            yield tree
            
            with ContentSwitcher(id="right-pane", initial="context-view"):
                yield ContextManagementView(id="context-view")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Tree).focus()

if __name__ == "__main__":
    app = ShowcaseApp()
    app.run()