"""Probe: which expand-then-move strategy lands the cursor on a revealed child?"""

import asyncio
from typing import Any

from textual.app import App, ComposeResult
from textual.widgets import Tree


class ProbeTree(Tree):
    def _lineage(self, node: Any) -> list[Any]:
        chain = []
        current = node
        while current is not None:
            chain.append(current)
            current = current.parent
        return list(reversed(chain))

    def jump_deferred(self, node: Any) -> None:
        for ancestor in self._lineage(node):
            ancestor.expand()
        self.call_after_refresh(self.move_cursor, node)

    def jump_layout_refresh(self, node: Any) -> None:
        for ancestor in self._lineage(node):
            ancestor.expand()
        self.refresh(layout=True)
        self.move_cursor(node)


class Probe(App):
    def compose(self) -> ComposeResult:
        yield ProbeTree("root")


async def scenario(strategy: str) -> None:
    app = Probe()
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(ProbeTree)
        tree.show_root = False
        parent = tree.root.add("parent", data="PARENT")
        child = parent.add_leaf("child", data="CHILD")
        tree.root.add("sibling", data="SIBLING")
        tree.move_cursor(parent)
        await pilot.pause()

        getattr(tree, strategy)(child)
        print(
            f"[{strategy}] after call: cursor={tree.cursor_node.data} "
            f"child.line={child.line} cursor_line={tree.cursor_line}"
        )
        await pilot.pause()
        print(
            f"[{strategy}] after pause: cursor={tree.cursor_node.data} "
            f"child.line={child.line} cursor_line={tree.cursor_line}"
        )


async def main() -> None:
    for strategy in ("jump_deferred", "jump_layout_refresh"):
        await scenario(strategy)


asyncio.run(main())
