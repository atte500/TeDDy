"""Regression: the interactive MESSAGE ask header renders on a terminal.

A communicating turn is dispatched as a single MESSAGE action whose body is
passed to ``IUserInteractor.ask_question``. ``_display_ask_header`` must render
that body through ``render_message_body`` when the console is a terminal and
keep the raw Markdown byte-identical otherwise, so pipeline and redirected
output do not change.

Before the fix the body was echoed with plain ``typer.echo`` on every path, so a
terminal showed literal ``**`` and inline backticks.
"""

import io
import re

from rich.console import Console
from tests.harness.setup.mocking import POSIXPathMock

from teddy_executor.adapters.outbound.console_interactor import (
    ConsoleInteractorAdapter,
)
from teddy_executor.core.utils.message_renderer import inline_code_theme

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

MESSAGE_BODY = (
    "## Heads up\n"
    "\n"
    "- **Bold** should lose its asterisks.\n"
    "- Inline `teddy resume -p` should lose backticks.\n"
)


def _adapter(console: Console, mock_env) -> ConsoleInteractorAdapter:
    config = POSIXPathMock()
    config.get_setting.return_value = None
    return ConsoleInteractorAdapter(
        system_env=mock_env, config_service=config, console=console
    )


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def test_ask_header_renders_body_on_terminal(mock_env) -> None:
    stream = io.StringIO()
    console = Console(file=stream, force_terminal=True, theme=inline_code_theme())
    adapter = _adapter(console, mock_env)

    adapter._display_ask_header(MESSAGE_BODY, None, "TeDDy")

    rendered = _strip_ansi(stream.getvalue())
    assert "**Bold**" not in rendered
    assert "`teddy resume -p`" not in rendered
    assert "Bold should lose its asterisks" in rendered


def test_ask_header_echoes_raw_body_off_terminal(mock_env, capsys) -> None:
    stream = io.StringIO()
    console = Console(file=stream, force_terminal=False)
    adapter = _adapter(console, mock_env)

    adapter._display_ask_header(MESSAGE_BODY, None, "TeDDy")

    captured = capsys.readouterr()
    assert "**Bold**" in captured.err
    assert "`teddy resume -p`" in captured.err
