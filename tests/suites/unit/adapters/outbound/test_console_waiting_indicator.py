"""Unit tests: the waiting indicator's stderr live region.

``WaitingIndicator`` owns the one transient line beneath the telemetry. It
starts a terminal-gated live region, renders ``{glyph} {message}`` on a callable
the region re-invokes so successive refreshes advance the glyph, and erases the
region on ``end`` so the settled layout stays byte-identical to a run without
the feature. The region arrives through an injected factory and the
interpreter-exit hook through an injected registry, so every branch is driven
deterministically: no sleeps, no refresh thread, and no global patching.
"""

import io
import logging
from typing import Any, Callable

from rich.console import Console
from rich.text import Text

from teddy_executor.adapters.outbound.console_waiting_indicator import (
    SPINNER_FRAMES,
    SPINNER_REFRESH_PER_SECOND,
    WaitingIndicator,
    create_live,
)

LABEL = "Waiting for pathfinder to respond..."
NEXT_LABEL = "Waiting for architect to respond..."


class RecordingLive:
    """A live-region double recording its lifecycle and rendering on demand."""

    def __init__(
        self,
        *,
        console: Console,
        get_renderable: Callable[[], Any],
        **kwargs: Any,
    ) -> None:
        self.console = console
        self.kwargs = kwargs
        self._get_renderable = get_renderable
        self.start_count = 0
        self.stop_count = 0

    def start(self) -> None:
        self.start_count += 1

    def stop(self) -> None:
        self.stop_count += 1

    def render(self) -> str:
        return self._get_renderable().plain


class RecordingLiveFactory:
    """Builds recording regions so the indicator's wiring stays assertable."""

    def __init__(self) -> None:
        self.created: list[RecordingLive] = []

    def __call__(
        self, console: Console, get_renderable: Callable[[], Any]
    ) -> RecordingLive:
        live = RecordingLive(console=console, get_renderable=get_renderable)
        self.created.append(live)
        return live


class RecordingExitHooks:
    """Stands in for ``atexit``: records registrations and fires them on demand."""

    def __init__(self) -> None:
        self.registered: list[Callable[[], None]] = []

    def register(self, hook: Callable[[], None]) -> None:
        self.registered.append(hook)

    def unregister(self, hook: Callable[[], None]) -> None:
        if hook in self.registered:
            self.registered.remove(hook)

    def fire_outstanding(self) -> None:
        for hook in list(self.registered):
            hook()


def _terminal_console() -> Console:
    return Console(file=io.StringIO(), force_terminal=True)


def _redirected_console() -> Console:
    return Console(file=io.StringIO(), force_terminal=False)


def _indicator(
    console: Console,
) -> tuple[WaitingIndicator, RecordingLiveFactory, RecordingExitHooks]:
    factory = RecordingLiveFactory()
    hooks = RecordingExitHooks()
    indicator = WaitingIndicator(
        console=console, live_factory=factory, exit_hooks=hooks
    )
    return indicator, factory, hooks


def test_redirected_stderr_renders_nothing() -> None:
    indicator, factory, hooks = _indicator(_redirected_console())

    # Act
    indicator.begin(LABEL)
    indicator.end()

    # Assert: animation control characters would corrupt redirected logs.
    assert factory.created == []
    assert hooks.registered == []


def test_the_region_opens_on_the_injected_console() -> None:
    console = _terminal_console()
    indicator, factory, _ = _indicator(console)

    # Act
    indicator.begin(LABEL)

    # Assert: one region, drawn on the console the adapter already owns.
    assert len(factory.created) == 1
    live = factory.created[0]
    assert live.console is console
    assert live.start_count == 1
    assert live.stop_count == 0


def test_the_transient_line_carries_one_glyph_and_the_label() -> None:
    indicator, factory, _ = _indicator(_terminal_console())

    # Act
    indicator.begin(LABEL)

    # Assert: the core owns the wording, the indicator owns how it is drawn.
    glyph, _, label = factory.created[0].render().partition(" ")
    assert glyph == SPINNER_FRAMES[0]
    assert label == LABEL


def test_successive_refreshes_advance_the_glyph() -> None:
    indicator, factory, _ = _indicator(_terminal_console())

    # Act: the region re-invokes the renderable on every refresh.
    indicator.begin(LABEL)
    live = factory.created[0]
    first = live.render()
    second = live.render()

    # Assert: from a frame counter, never the clock, so the wait looks alive
    # without a timestamp entering the assertion.
    assert first.startswith(SPINNER_FRAMES[0])
    assert second.startswith(SPINNER_FRAMES[1])
    assert first != second


def test_end_erases_the_region_and_forgets_the_exit_hook() -> None:
    indicator, factory, hooks = _indicator(_terminal_console())

    indicator.begin(LABEL)

    # Act
    indicator.end()

    # Assert: the transient line is gone and no exit hook outlives the wait.
    assert factory.created[0].stop_count == 1
    assert hooks.registered == []


def test_an_unbalanced_end_is_a_silent_noop() -> None:
    indicator, factory, hooks = _indicator(_terminal_console())

    # Act: a defensive ``finally`` may end a wait a failure already ended.
    indicator.end()
    indicator.end()

    # Assert: no region to stop, nothing left registered.
    assert factory.created == []
    assert hooks.registered == []


def test_a_nested_begin_replaces_the_label_without_stacking_a_region() -> None:
    indicator, factory, hooks = _indicator(_terminal_console())

    indicator.begin(LABEL)

    # Act
    indicator.begin(NEXT_LABEL)

    # Assert: only one line may be owned at a time.
    assert len(factory.created) == 1
    live = factory.created[0]
    assert live.start_count == 1
    assert live.render().endswith(NEXT_LABEL)
    assert len(hooks.registered) == 1


def test_the_region_registers_one_exit_hook_for_the_wait() -> None:
    indicator, _, hooks = _indicator(_terminal_console())

    # Act
    indicator.begin(LABEL)
    during = len(hooks.registered)
    indicator.end()

    # Assert: exactly one hook while the region is open, none after it closes.
    assert during == 1
    assert hooks.registered == []


def test_the_exit_hook_stops_a_region_abandoned_by_a_daemon_worker() -> None:
    indicator, factory, hooks = _indicator(_terminal_console())

    indicator.begin(LABEL)
    live = factory.created[0]

    # Act: the process exits while the region is still open on the worker, so
    # its own ``finally`` never runs.
    hooks.fire_outstanding()

    # Assert: the region is gone, the hook is forgotten, and the late ``end``
    # cannot stop it a second time.
    assert live.stop_count == 1
    assert hooks.registered == []

    indicator.end()

    assert live.stop_count == 1


def test_the_production_factory_never_redirects_stdout_or_stderr() -> None:
    console = _terminal_console()

    def _render() -> Text:
        return Text(SPINNER_FRAMES[0])

    # Act
    live = create_live(console, _render, RecordingLive)

    # Assert: rich enables redirection unconditionally on ``start``, so the
    # defaults would swap the process-global streams from the daemon worker.
    assert live.console is console
    assert live.kwargs["transient"] is True
    assert live.kwargs["redirect_stdout"] is False
    assert live.kwargs["redirect_stderr"] is False
    assert live.kwargs["refresh_per_second"] == SPINNER_REFRESH_PER_SECOND
    assert live.render() == SPINNER_FRAMES[0]


class _FailingLive(RecordingLive):
    """A region whose lifecycle fails, standing in for a broken terminal."""

    def __init__(self, *, fail_on: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.fail_on = fail_on

    def start(self) -> None:
        if self.fail_on == "start":
            raise OSError("terminal went away")
        super().start()

    def stop(self) -> None:
        if self.fail_on == "stop":
            raise OSError("terminal went away")
        super().stop()


class _FailingLiveFactory:
    """Builds failing regions so the never-raise contract is observable."""

    def __init__(self, fail_on: str) -> None:
        self.fail_on = fail_on
        self.created: list[_FailingLive] = []

    def __call__(
        self, console: Console, get_renderable: Callable[[], Any]
    ) -> _FailingLive:
        live = _FailingLive(
            fail_on=self.fail_on, console=console, get_renderable=get_renderable
        )
        self.created.append(live)
        return live


def _failing_indicator(fail_on: str) -> tuple[WaitingIndicator, RecordingExitHooks]:
    hooks = RecordingExitHooks()
    indicator = WaitingIndicator(
        console=_terminal_console(),
        live_factory=_FailingLiveFactory(fail_on),
        exit_hooks=hooks,
    )
    return indicator, hooks


def test_a_failing_region_start_never_breaks_the_wait(caplog) -> None:
    indicator, hooks = _failing_indicator("start")

    # Act / Assert: the wait is a display detail, so it cannot abort the turn —
    # ``begin_waiting`` runs outside the planning ``try``.
    with caplog.at_level(logging.DEBUG):
        indicator.begin(LABEL)
        indicator.end()

    # Assert: reported, not silently swallowed, and nothing left registered.
    assert "terminal went away" in caplog.text
    assert hooks.registered == []


def test_a_failing_region_stop_never_breaks_the_unwind(caplog) -> None:
    indicator, hooks = _failing_indicator("stop")

    indicator.begin(LABEL)

    # Act / Assert: teardown runs in a ``finally``, so raising would corrupt
    # the error that ended the wait.
    with caplog.at_level(logging.DEBUG):
        indicator.end()

    assert "terminal went away" in caplog.text
    assert hooks.registered == []

    # Assert: a repeated end stays silent rather than tearing down twice.
    indicator.end()
