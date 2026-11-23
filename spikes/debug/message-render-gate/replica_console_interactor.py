"""Replica of ConsoleInteractorAdapter with the MESSAGE body rendered.

Only two members differ from production:

* ``__init__`` builds a themed stderr console (``inline_code_theme``) and
  accepts an injected console as a test seam.
* ``_display_ask_header`` routes the body through ``render_message_body`` when
  the console is a terminal, keeping the raw ``typer.echo`` fallback otherwise.

Every other method is inherited unchanged from the production module.
"""

from typing import Optional

import typer
from rich.console import Console

from teddy_executor.adapters.outbound.console_interactor import (
    ConsoleInteractorAdapter as ProductionConsoleInteractorAdapter,
)
from teddy_executor.core.utils.message_renderer import (
    inline_code_theme,
    render_message_body,
)


class ConsoleInteractorAdapter(ProductionConsoleInteractorAdapter):
    def __init__(self, system_env, config_service, console: Optional[Console] = None):
        super().__init__(system_env, config_service)
        self._console = console if console is not None else Console(
            theme=inline_code_theme(), stderr=True
        )

    def _display_ask_header(self, prompt, resources, agent_name):
        display_name = agent_name if agent_name else "TeDDy"
        header = f"\n--- MESSAGE from {display_name} ---"
        typer.secho(header, fg=typer.colors.CYAN, err=True)
        if self._console.is_terminal:
            render_message_body(prompt, self._console)
        else:
            typer.echo(prompt, err=True)
        if resources:
            typer.echo("\n▶ Reference Files:", err=True)
            typer.echo("\n".join(resources), err=True)
        typer.echo("", err=True)
