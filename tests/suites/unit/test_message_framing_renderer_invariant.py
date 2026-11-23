"""Structural guard: every typer MESSAGE framing must route through the renderer.

Two production surfaces print the ``--- MESSAGE from ... ---`` framing to the
terminal: the session orchestrator's pipeline/``resume -p`` printer and the
interactive ask header. Both must render the body through
``render_message_body`` when the output is a terminal, or the agent's Markdown
reaches the user raw. This guard scans every production module that prints the
framing through typer and asserts it references the renderer, so a future
framing surface cannot silently reintroduce the defect.
"""

from pathlib import Path

import teddy_executor


def _production_python_files() -> list[Path]:
    package_root = Path(teddy_executor.__file__).parent
    return sorted(package_root.rglob("*.py"))


def test_every_typer_message_framing_surface_references_renderer() -> None:
    framing = "--- MESSAGE from"
    offenders: list[str] = []
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        uses_typer = "typer.secho" in text or "typer.echo" in text
        if framing in text and uses_typer and "render_message_body" not in text:
            offenders.append(str(path))
    assert offenders == [], (
        "Every module that prints the MESSAGE framing through typer must route "
        f"the body through render_message_body; offenders: {offenders}"
    )
