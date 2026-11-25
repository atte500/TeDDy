"""Structural guard: Rich Markdown prose renders only through the renderer.

Rich lays a ``rich.markdown.Markdown`` renderable out at ``console.width`` and
emits hard newlines, so prose printed that way can never reflow when the
terminal is resized. ``message_renderer`` is the one module allowed to build
that renderable, because it lays prose out at an unbounded width and hands the
fold to the terminal. Any other production import of ``rich.markdown``
reintroduces print-width hard wrapping on a new surface, so this guard scans
the package for such imports and asserts the offender list is empty.

The Textual TUI imports ``Markdown`` from ``textual.widgets``, a different
module path that reflows natively, so keying on ``rich.markdown`` imports
cannot flag it.
"""

import re
from pathlib import Path

import teddy_executor

_RICH_MARKDOWN_IMPORT = re.compile(
    r"^\s*(?:from\s+rich\.markdown\s+import|import\s+rich\.markdown)",
    re.MULTILINE,
)


def _production_python_files() -> list[Path]:
    package_root = Path(teddy_executor.__file__).parent
    return sorted(package_root.rglob("*.py"))


def test_rich_markdown_imports_are_confined_to_the_message_renderer() -> None:
    renderer = (
        Path(teddy_executor.__file__).parent / "core" / "utils" / "message_renderer.py"
    )
    offenders = [
        str(path)
        for path in _production_python_files()
        if path != renderer
        and _RICH_MARKDOWN_IMPORT.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], (
        "Only core/utils/message_renderer.py may import rich.markdown: Rich "
        "folds that renderable at the console width and the hard newlines stop "
        f"a resize from reflowing the text; offenders: {offenders}"
    )
