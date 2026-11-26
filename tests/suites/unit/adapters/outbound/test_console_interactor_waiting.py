"""Unit tests: the console adapter's waiting delegation.

``ConsoleInteractorAdapter`` owns no rendering of the wait: both operations are
forwarded to the ``IWaitingIndicator`` it holds, so the transient line has one
implementation. The indicator arrives through constructor injection, so the
delegation is observed without a live region.
"""

import io

from rich.console import Console

from teddy_executor.adapters.outbound.console_interactor import (
    ConsoleInteractorAdapter,
)
from teddy_executor.adapters.outbound.console_waiting_indicator import (
    IWaitingIndicator,
)
from tests.harness.setup.mocking import POSIXPathMock

LABEL = "Waiting for pathfinder to respond..."


class RecordingIndicator:
    """A duck-typed indicator recording the waits it was asked to draw."""

    def __init__(self) -> None:
        self.begun: list[str] = []
        self.ends = 0

    def begin(self, message: str) -> None:
        self.begun.append(message)

    def end(self) -> None:
        self.ends += 1


def _adapter(indicator: IWaitingIndicator) -> ConsoleInteractorAdapter:
    config = POSIXPathMock()
    config.get_setting.return_value = None
    return ConsoleInteractorAdapter(
        system_env=POSIXPathMock(),
        config_service=config,
        console=Console(file=io.StringIO(), force_terminal=False),
        waiting_indicator=indicator,
    )


def test_begin_waiting_delegates_the_label() -> None:
    indicator = RecordingIndicator()

    # Act
    _adapter(indicator).begin_waiting(LABEL)

    # Assert: the indicator owns how the line is drawn.
    assert indicator.begun == [LABEL]


def test_end_waiting_delegates_the_teardown() -> None:
    indicator = RecordingIndicator()
    adapter = _adapter(indicator)

    adapter.begin_waiting(LABEL)

    # Act
    adapter.end_waiting()

    # Assert
    assert indicator.ends == 1
