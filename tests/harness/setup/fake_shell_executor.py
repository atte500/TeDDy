"""FakeShellExecutor: in-memory IShellExecutor conformance double.

Acceptance tests that drive an EXECUTE action need a shell that spawns no
subprocess, touches no network, and never sleeps. This double records the
commands it was asked to run and returns a caller-supplied ``ShellOutput``.

The interrupt scenario needs the press to land while the orchestrator holds its
EXECUTING phase, so the double accepts an injected ``on_execute`` callback that
runs inside ``execute()`` and supplies the output. The caller therefore decides
what a "killed" command returns, and the double stays press-agnostic.

Anti-mock-poisoning: a plain class with constructor-set state (not a dynamic
mock), mirroring ``FakeQuitKeyListener`` / ``FakeHTTPResponse``. It subclasses
``IShellExecutor`` so a signature drift fails static checking instead of
silently diverging from the port.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from teddy_executor.core.domain.models.shell_output import ShellOutput
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor

ExecuteCallback = Callable[[str], ShellOutput]


class FakeShellExecutor(IShellExecutor):
    """In-memory IShellExecutor double recording every dispatched command."""

    def __init__(
        self,
        output: Optional[ShellOutput] = None,
        on_execute: Optional[ExecuteCallback] = None,
    ) -> None:
        self._default_output: ShellOutput = (
            output
            if output is not None
            else ShellOutput(stdout="", stderr="", return_code=0)
        )
        self._on_execute = on_execute
        self.commands: list[str] = []

    # The six-parameter signature is the IShellExecutor contract itself, so
    # the argument count is fixed by the port rather than by this double.
    def execute(  # noqa: PLR0913
        self,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        background: bool = False,
        max_lines: Optional[int] = None,
    ) -> ShellOutput:
        """Record the command, then return the scripted or injected output."""
        self.commands.append(command)
        if self._on_execute is not None:
            return self._on_execute(command)
        return self._default_output
