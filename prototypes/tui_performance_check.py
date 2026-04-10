from textual.app import App, ComposeResult
from textual.widgets import Label, Static, ListView, ListItem, Header, Footer
from textual.containers import Vertical

LARGE_CONTENT = "Line item content " * 10000 # ~170KB string

class PerformanceApp(App):
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Label("Select an item to see if it freezes")
            yield ListView(
                ListItem(Label("Item with Static (Fast)")),
                ListItem(Label("Item with Label (Slow/Freeze)")),
                id="list"
            )
            # This is where we show the detail
            yield Static(id="detail-static")
            yield Label(id="detail-label")
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        static = self.query_one("#detail-static", Static)
        label = self.query_one("#detail-label", Label)

        if "Static" in str(event.item.children[0].renderable):
            static.update(LARGE_CONTENT)
            label.update("")
        else:
            # This is expected to be slow or freeze the UI during layout
            static.update("")
            label.update(LARGE_CONTENT)

if __name__ == "__main__":
    app = PerformanceApp()
    app.run()
