"""Unit tests: console stdin-ownership claims (Bug 56 bare-`q`).

The wired terminal quit-key reader backs off while ``is_stdin_owned()`` is
True. The console's interactive read sites must therefore CLAIM
``stdin_owned()`` while they read from stdin; otherwise the wired reader would
``os.read``-consume a keystroke (including a ``q``) meant for a prompt (the
reader's ``_process_byte`` discards non-quit bytes).

Each test injects a hand-rolled probe double at the site's leaf stdin read(s)
that records ``is_stdin_owned()`` at call time, asserting ownership is claimed
DURING the read and RELEASED after. No dynamic mocks (anti-mock-poisoning).
"""

import pytest

from teddy_executor.adapters.outbound.console_interactor import (
    ConsoleInteractorAdapter,
)
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.utils.stdin_ownership import is_stdin_owned
from tests.harness.setup.mocking import POSIXPathMock


class _OwnershipProbe:
    """Hand-rolled stdin-read probe recording is_stdin_owned() at call time.

    Stands in for the leaf stdin read at each site (``typer.prompt``,
    ``_launch_editor_synchronous``, ``_pt_prompt``) and records whether stdin
    was owned at the moment of the read.
    """

    def __init__(self, return_value):
        self._return_value = return_value
        self.observed = []

    def __call__(self, *_args, **_kwargs):
        self.observed.append(is_stdin_owned())
        return self._return_value


@pytest.fixture
def adapter(mock_env) -> ConsoleInteractorAdapter:
    mock_config = POSIXPathMock()
    mock_config.get_setting.return_value = None
    return ConsoleInteractorAdapter(system_env=mock_env, config_service=mock_config)


def _plan() -> Plan:
    return Plan(
        title="Test Plan",
        rationale="Rationale",
        actions=[ActionData(type="EXECUTE", params={"command": "true"})],
    )


class TestPromptClaimsOwnership:
    def test_prompt_claims_stdin_ownership_during_read(self, adapter, monkeypatch):
        probe = _OwnershipProbe("answer")
        monkeypatch.setattr("typer.prompt", probe)

        adapter.prompt("Q?")

        assert probe.observed == [True], "prompt must claim stdin while reading"
        assert is_stdin_owned() is False, "ownership must be released after the read"


class TestConfirmPlanReviewClaimsOwnership:
    def test_confirm_plan_review_claims_stdin_ownership_during_read(
        self, adapter, monkeypatch
    ):
        probe = _OwnershipProbe("y")
        monkeypatch.setattr("typer.prompt", probe)

        adapter.confirm_plan_review(_plan())

        assert probe.observed == [True]
        assert is_stdin_owned() is False


class TestConfirmActionClaimsOwnership:
    def test_confirm_action_claims_stdin_ownership_during_read(
        self, adapter, monkeypatch
    ):
        probe = _OwnershipProbe("y")
        monkeypatch.setattr("typer.prompt", probe)

        adapter.confirm_action(
            action=ActionData(type="test", params={}), action_prompt="?"
        )

        assert probe.observed == [True]
        assert is_stdin_owned() is False


class TestConfirmManualHandoffClaimsOwnership:
    def test_confirm_manual_handoff_claims_stdin_ownership_during_read(
        self, adapter, monkeypatch
    ):
        probe = _OwnershipProbe("")  # empty response -> approved
        monkeypatch.setattr("typer.prompt", probe)

        adapter.confirm_manual_handoff(
            action_type="MESSAGE",
            target_agent="assistant",
            resources=[],
            message="hi",
        )

        assert probe.observed == [True]
        assert is_stdin_owned() is False


class TestPromptForMessageClaimsOwnership:
    def test_prompt_for_message_claims_stdin_ownership_during_editor(
        self, adapter, monkeypatch
    ):
        monkeypatch.delenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", raising=False)
        probe = _OwnershipProbe("edited")
        monkeypatch.setattr(adapter, "_launch_editor_synchronous", probe)

        adapter.prompt_for_message()

        assert probe.observed == [True]
        assert is_stdin_owned() is False


class TestAskLoopRunClaimsOwnership:
    def test_ask_loop_run_claims_stdin_ownership_during_read(
        self, adapter, monkeypatch
    ):
        probe = _OwnershipProbe("hello")
        monkeypatch.setattr(adapter._ask_loop, "_pt_prompt", probe)

        result = adapter._ask_loop.run("prompt")

        assert result == "hello"
        assert probe.observed == [True]
        assert is_stdin_owned() is False
