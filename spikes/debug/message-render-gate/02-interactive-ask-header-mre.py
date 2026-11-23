"""MRE: does the interactive MESSAGE ask header echo the agent body raw?

A communicating turn is dispatched as a single MESSAGE action whose body is
passed verbatim to ``IUserInteractor.ask_question``. Production echoes the body
with ``typer.echo`` inside ``_display_ask_header``, before rendering; the
replica routes it through ``render_message_body`` on a terminal.

Set MRE_TARGET=production|replica and run once under a pty, once piped.
"""

import os
import sys
from types import SimpleNamespace

from rich.console import Console

from teddy_executor.core.utils.message_renderer import inline_code_theme

BODY = """## Heads up

- **Bold** should lose its asterisks.
- Inline `teddy resume -p` should lose backticks.

```bash
echo hi
```
"""

TARGET = os.environ.get("MRE_TARGET", "production")


def _adapter_class():
    if TARGET == "replica":
        from replica_console_interactor import ConsoleInteractorAdapter

        return ConsoleInteractorAdapter
    from teddy_executor.adapters.outbound.console_interactor import (
        ConsoleInteractorAdapter,
    )

    return ConsoleInteractorAdapter


def main() -> None:
    adapter = object.__new__(_adapter_class())
    adapter._console = Console(theme=inline_code_theme(), stderr=True)
    adapter._ask_loop = SimpleNamespace(run=lambda prompt: "")
    print(
        f"MRE_TARGET={TARGET} stderr_isatty={sys.stderr.isatty()} "
        f"console_is_terminal={adapter._console.is_terminal} "
        f"TERM={os.environ.get('TERM')!r}",
        file=sys.stderr,
    )
    print("BEGIN_HEADER", file=sys.stderr)
    adapter.ask_question(BODY, ["docs/x.md"], "TeDDy")
    print("END_HEADER", file=sys.stderr)


if __name__ == "__main__":
    main()
