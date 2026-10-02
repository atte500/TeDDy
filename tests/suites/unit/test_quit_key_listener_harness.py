"""Harness tests: the shared in-memory IQuitKeyListener conformance double.

The real terminal quit-key reader drives a TTY and is an explicit no-op
off-TTY (Bug 56), so its start()/stop() lifecycle is unobservable in an
in-process test. The Wiring boundary test therefore needs an injected
in-memory double it can observe. ``FakeQuitKeyListener`` is that double: a
hand-rolled (not a dynamic mock) ``IQuitKeyListener`` conformance that
records its ``start()``/``stop()`` lifecycle and exposes a ``fire_quit()``
hook to trigger the injected ``on_quit`` callback.

Mirrors the established harness-double convention (``FakeHTTPResponse``,
``FakeRegistryCache``): a plain class with constructor-set state.
"""

from teddy_executor.core.ports.outbound.quit_key_listener import IQuitKeyListener
from tests.harness.setup.fake_quit_key_listener import FakeQuitKeyListener


class _QuitRecorder:
    """Hand-rolled call recorder (not a mock) counting invocations."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


def test_fake_quit_key_listener_conforms_to_the_port():
    """The double satisfies the runtime-checkable IQuitKeyListener port."""
    fake = FakeQuitKeyListener()

    assert isinstance(fake, IQuitKeyListener)


def test_fake_records_start_and_stop_lifecycle_invocation_order():
    """start()/stop() are recorded in invocation order for boundary assertions."""
    fake = FakeQuitKeyListener()

    fake.start()
    fake.stop()

    assert fake.lifecycle == ["start", "stop"]


def test_fire_quit_invokes_the_injected_on_quit_callback():
    """The fire_quit() hook triggers the Constructor-Injected on_quit callback."""
    recorder = _QuitRecorder()
    fake = FakeQuitKeyListener(on_quit=recorder)

    fake.fire_quit()

    assert recorder.calls == 1


def test_fire_quit_without_a_callback_is_a_safe_noop():
    """Firing a quit with no injected hook must not raise or mutate the lifecycle."""
    fake = FakeQuitKeyListener()

    fake.fire_quit()  # must not raise

    assert fake.lifecycle == []
