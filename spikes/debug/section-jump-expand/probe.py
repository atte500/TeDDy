"""Probe: is a move onto a just-revealed child swallowed by Tree.move_cursor?"""

import asyncio

from textual.app import App, ComposeResult
from textual.widgets import Tree


class Probe(App):
    def compose(self) -> ComposeResult:
        yield Tree("root")


async def main() -> None:
    app = Probe()
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(Tree)
        tree.show_root = False

        parent = tree.root.add("parent", data="PARENT")
        child = parent.add_leaf("child", data="CHILD")
        sibling = tree.root.add("sibling", data="SIBLING")

        tree.move_cursor(parent)
        await pilot.pause()
        print("cursor seeded on:", tree.cursor_node.data)
        print("child.line while collapsed:", child.line)

        parent.expand()
        print("child.line right after expand():", child.line)
        tree.move_cursor(child)
        print("cursor immediately after expand+move:", tree.cursor_node.data)

        await pilot.pause()
        print("child.line after pause:", child.line)
        print("cursor after pause:", tree.cursor_node.data)

        tree.move_cursor(child)
        print("cursor after second move:", tree.cursor_node.data)

        tree.move_cursor(sibling)
        parent.expand()
        tree.move_cursor(child)
        print("cursor after sibling+expand+move:", tree.cursor_node.data)


asyncio.run(main())
