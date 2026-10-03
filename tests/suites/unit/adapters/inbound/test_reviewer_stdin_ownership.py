"""Unit test: the Textual reviewer claims stdin ownership while the TUI runs.

The session-level quit-key reader polls stdin for the whole turn loop (Bug 58
made it persistent). While the Textual TUI owns the keyboard it must claim
``stdin_owned()`` so the reader backs off and the TUI's own bindings (e.g.
``q`` to cancel) keep working. `stdin_owned` is the established back-off
contract consulted by the reader's ``_read_loop``.
"""

from unittest.mock import Mock

from teddy_executor.adapters.inbound import textual_plan_reviewer as module
from teddy_executor.adapters.inbound.textual_plan_reviewer import TextualPlanReviewer
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.utils.stdin_ownership import is_stdin_owned


def test_review_claims_stdin_ownership_while_the_tui_runs(monkeypatch):
    observed: dict[str, bool] = {}

    class _RecordingApp:
        """Textual-app double recording stdin ownership during run()."""

        def __init__(self, **_kwargs) -> None:
            pass

        def run(self):
            observed["owned_during_run"] = is_stdin_owned()

    monkeypatch.setattr(module, "ReviewerApp", _RecordingApp)

    reviewer = TextualPlanReviewer(
        system_env=Mock(spec=ISystemEnvironment),
        file_system=Mock(spec=IFileSystemManager),
        console_tooling=Mock(spec=ConsoleToolingHelper),
        action_dispatcher=Mock(spec=ActionDispatcher),
    )

    reviewer.review(plan=Mock(spec=Plan))

    # Assert: ownership was claimed for the app's lifetime and released after.
    assert observed["owned_during_run"] is True
    assert is_stdin_owned() is False
