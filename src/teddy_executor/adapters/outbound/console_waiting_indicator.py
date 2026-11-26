"""The transient stderr live region drawn while a plan is generated.

A slow model leaves the terminal frozen: the waiting banner prints once and
nothing moves until the plan arrives. ``WaitingIndicator`` owns exactly one
transient line beneath the telemetry, gated on an attached terminal, and erases
it on completion so the settled layout stays byte-identical to a run without
the feature.

Two rich realities shape the production factory. ``Live.start`` enables stdout
and stderr redirection unconditionally rather than only for full-screen mode, so
the factory disables both; otherwise a worker thread would swap the
process-global streams. And ``rich.live`` registers no exit hook of its own, so
a region abandoned by a killed daemon worker would leave the cursor hidden —
hence the hook the indicator registers for the duration of the wait.
"""

from __future__ import annotations

import atexit
import logging
from typing import Callable, Protocol, TypeVar

from rich.console import Console
from rich.live import Live
from rich.text import Text

logger = logging.getLogger(__name__)

SPINNER_FRAMES: tuple[str, ...] = tuple("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
SPINNER_REFRESH_PER_SECOND = 10


class IWaitingIndicator(Protocol):
    """The waiting surface the console interactor delegates to."""

    def begin(self, message: str) -> None: ...

    def end(self) -> None: ...


class ILiveRegion(Protocol):
    """The slice of a rich ``Live`` region the indicator drives."""

    def start(self) -> None: ...

    def stop(self) -> None: ...


class IExitHooks(Protocol):
    """The two-operation slice of an exit-hook registry the indicator drives."""

    def register(self, hook: Callable[[], None]) -> None: ...

    def unregister(self, hook: Callable[[], None]) -> None: ...


class AtexitExitHooks:
    """Adapts the ``atexit`` module to ``IExitHooks``.

    ``atexit.register`` returns the callable and accepts forwarded arguments, so
    the module implements both operations without being structurally assignable
    to this protocol. Narrowing it here is what lets the production bind site
    type-check instead of being silenced with a cast.
    """

    def register(self, hook: Callable[[], None]) -> None:
        atexit.register(hook)

    def unregister(self, hook: Callable[[], None]) -> None:
        atexit.unregister(hook)


LiveFactory = Callable[[Console, Callable[[], Text]], ILiveRegion]

LiveRegionT = TypeVar("LiveRegionT", bound=ILiveRegion)


def create_live(
    console: Console,
    get_renderable: Callable[[], Text],
    live_class: Callable[..., LiveRegionT],
) -> LiveRegionT:
    """Build the live region for one wait, typed as the class handed in.

    ``live_class`` is supplied by the caller, so the composition site binds
    ``Live`` and a test can bind a recording double — and receive that double
    back, so its own lifecycle stays observable through the concrete type.
    """
    return live_class(
        console=console,
        get_renderable=get_renderable,
        transient=True,
        redirect_stdout=False,
        redirect_stderr=False,
        refresh_per_second=SPINNER_REFRESH_PER_SECOND,
    )


def _production_live_factory(
    console: Console, get_renderable: Callable[[], Text]
) -> ILiveRegion:
    """Build one production region from rich's ``Live``."""
    return create_live(console, get_renderable, Live)


def create_indicator(console: Console) -> WaitingIndicator:
    """Build the production indicator for ``console``.

    This is the one place the production region and the interpreter-exit
    registry are bound, so the indicator stays constructible from recording
    doubles.
    """
    return WaitingIndicator(
        console=console,
        live_factory=_production_live_factory,
        exit_hooks=AtexitExitHooks(),
    )


class WaitingIndicator:
    """Owns the one transient line drawn for the duration of a model call."""

    def __init__(
        self,
        console: Console,
        live_factory: LiveFactory,
        exit_hooks: IExitHooks,
    ) -> None:
        assert console is not None, "WaitingIndicator requires a console"
        assert live_factory is not None, "WaitingIndicator requires a live factory"
        assert exit_hooks is not None, "WaitingIndicator requires an exit registry"
        self._console = console
        self._live_factory = live_factory
        self._exit_hooks = exit_hooks
        self._live: ILiveRegion | None = None
        self._message = ""
        self._frame = 0
        # One stable bound method, so the registry can remove the very hook it
        # was given instead of matching a freshly created bound method.
        self._teardown_hook = self._teardown

    def begin(self, message: str) -> None:
        """Open the region, or replace its label when one is already open."""
        if not self._console.is_terminal:
            return
        self._message = message
        if self._live is not None:
            return
        self._frame = 0
        try:
            live = self._live_factory(self._console, self._render)
            self._live = live
            self._exit_hooks.register(self._teardown_hook)
            live.start()
        except Exception as error:
            # Display-only: ``begin_waiting`` runs outside the planning ``try``,
            # so a broken terminal must never abort the turn. rich tears a
            # partially started region down itself, so no stop is issued here.
            logger.warning("The waiting indicator could not start: %s", error)
            self._live = None
            self._exit_hooks.unregister(self._teardown_hook)

    def end(self) -> None:
        """Erase the region; a no-op when no region is open."""
        if self._live is None:
            return
        self._teardown()

    def _render(self) -> Text:
        """Return the transient line, advancing one frame per refresh."""
        frame = SPINNER_FRAMES[self._frame % len(SPINNER_FRAMES)]
        self._frame += 1
        return Text(f"{frame} {self._message}", style="cyan")

    def _teardown(self) -> None:
        """Release the region and the exit hook that guards it."""
        live = self._live
        if live is None:
            return
        self._live = None
        self._exit_hooks.unregister(self._teardown_hook)
        try:
            live.stop()
        except Exception as error:
            # Teardown runs in a ``finally`` on the worker thread, so raising
            # here would corrupt the error that ended the wait.
            logger.warning("The waiting indicator could not stop cleanly: %s", error)
