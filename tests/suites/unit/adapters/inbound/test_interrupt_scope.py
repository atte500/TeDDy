"""Unit tests: the shared interrupt bracket seam.

``interrupt_scope(guard, listener)`` is the single owner of the bracket both
boundaries need: it takes the guard's SIGINT disposition, starts the quit-key
listener, and releases both in a ``finally`` on every exit path. Two owners
cannot each take their own snapshot, because they would restore each other's
handler.
"""

import signal
import time

import pytest
import typer

from teddy_executor.adapters.inbound.interrupt_scope import interrupt_scope
from teddy_executor.core.utils.interrupt_guard import InterruptGuard
from tests.harness.setup.fake_quit_key_listener import FakeQuitKeyListener


@pytest.fixture
def guard() -> InterruptGuard:
    return InterruptGuard(monotonic=time.monotonic)


@pytest.fixture
def original_disposition():
    """Restores the pre-test SIGINT disposition, even when an assertion fails."""
    previous = signal.getsignal(signal.SIGINT)
    yield previous
    signal.signal(signal.SIGINT, previous)


class TestBracketLifecycle:
    """The bracket takes both resources for its body and releases them after."""

    def test_installs_the_handler_and_starts_the_listener_for_the_body(
        self, guard, original_disposition
    ) -> None:
        listener = FakeQuitKeyListener()

        with interrupt_scope(guard, listener):
            assert signal.getsignal(signal.SIGINT) == guard._handle_signal
            assert listener.lifecycle == ["start"]

    def test_releases_the_disposition_and_stops_the_listener_on_exit(
        self, guard, original_disposition
    ) -> None:
        listener = FakeQuitKeyListener()

        with interrupt_scope(guard, listener):
            pass

        assert signal.getsignal(signal.SIGINT) is original_disposition
        assert listener.lifecycle == ["start", "stop"]

    def test_admits_a_second_bracket_after_the_first_released_its_claim(
        self, guard, original_disposition
    ) -> None:
        # One memoized container keeps a single guard alive across in-process
        # commands, so a released claim must not block the next bracket.
        listener = FakeQuitKeyListener()

        with interrupt_scope(guard, listener):
            pass
        with interrupt_scope(guard, listener):
            pass

        assert listener.lifecycle == ["start", "stop", "start", "stop"]
        assert signal.getsignal(signal.SIGINT) is original_disposition


class TestUnwindingPaths:
    """Every exit path releases the disposition and stops the listener."""

    def test_a_raising_action_still_releases_both(
        self, guard, original_disposition
    ) -> None:
        listener = FakeQuitKeyListener()

        with pytest.raises(RuntimeError):
            with interrupt_scope(guard, listener):
                raise RuntimeError("the action blew up")

        assert signal.getsignal(signal.SIGINT) is original_disposition
        assert listener.lifecycle == ["start", "stop"]

    def test_a_typer_exit_still_releases_both(
        self, guard, original_disposition
    ) -> None:
        # An exit code must not bypass restoration: a validation failure raises
        # typer.Exit through the same finally.
        listener = FakeQuitKeyListener()

        with pytest.raises(typer.Exit):
            with interrupt_scope(guard, listener):
                raise typer.Exit(code=1)

        assert signal.getsignal(signal.SIGINT) is original_disposition
        assert listener.lifecycle == ["start", "stop"]

    def test_a_keyboard_interrupt_propagates_after_release(
        self, guard, original_disposition
    ) -> None:
        # The seam never swallows an interrupt: the boundary owns the notice.
        listener = FakeQuitKeyListener()

        with pytest.raises(KeyboardInterrupt):
            with interrupt_scope(guard, listener):
                raise KeyboardInterrupt

        assert signal.getsignal(signal.SIGINT) is original_disposition
        assert listener.lifecycle == ["start", "stop"]


class TestReleaseOrdering:
    """The listener stops while the disposition is still the guard's."""

    def test_stops_the_listener_before_restoring_the_disposition(
        self, guard, original_disposition
    ) -> None:
        observed: list[object] = []

        class _DispositionRecordingListener(FakeQuitKeyListener):
            def stop(self) -> None:
                observed.append(signal.getsignal(signal.SIGINT))
                super().stop()

        with interrupt_scope(guard, _DispositionRecordingListener()):
            pass

        assert observed == [guard._handle_signal]


class TestPressState:
    """A bracket starts with no press recorded."""

    def test_entry_clears_a_press_source_left_by_a_previous_bracket(
        self, guard, original_disposition
    ) -> None:
        # A stale source would name the previous key in this run's notice.
        guard.record_source("q")
        listener = FakeQuitKeyListener()

        with interrupt_scope(guard, listener):
            assert guard.source is None
