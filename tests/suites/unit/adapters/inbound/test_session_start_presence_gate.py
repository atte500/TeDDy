"""Presence gate for the `teddy start` opening prompt.

Without a terminal and no ``-m``, the handler must exit with the existing
no-input message instead of entering the ask loop. With a terminal, the prompt
still fires and seeds the session. A supplied ``-m`` never consults presence.
"""

from unittest.mock import Mock

import pytest
import typer
from punq import Container

from teddy_executor.adapters.inbound import session_cli_handlers as handlers
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


class FakeSystemEnvironment:
    """Presence double that reports a fixed ``isatty()`` answer."""

    def __init__(self, isatty: bool) -> None:
        self._isatty = isatty
        self.isatty_calls = 0

    def isatty(self) -> bool:
        self.isatty_calls += 1
        return self._isatty


@pytest.fixture(autouse=True)
def _isolate_start(monkeypatch):
    """Strip the startup preamble and session loop from the handler under test."""
    monkeypatch.setattr(handlers, "_start_background_update_check", lambda *a, **k: [])
    monkeypatch.setattr(handlers, "_run_startup_preamble", lambda *a, **k: None)
    monkeypatch.setattr(handlers, "_echo_config_success", lambda *a, **k: None)
    monkeypatch.setattr(handlers, "_orchestrate_session_loop", lambda *a, **k: None)


def _build_container(system_env: FakeSystemEnvironment, *, reply: str):
    container = Container()
    session_manager = Mock(spec=ISessionManager)
    session_manager.create_session.return_value = "/tmp/sessions/new"
    user_interactor = Mock(spec=IUserInteractor)
    user_interactor.ask_question.return_value = reply

    container.register(IInitUseCase, instance=Mock(spec=IInitUseCase))
    container.register(IRunPlanUseCase, instance=Mock(spec=IRunPlanUseCase))
    container.register(ISessionManager, instance=session_manager)
    container.register(IUserInteractor, instance=user_interactor)
    container.register(ISessionLoopGuard, instance=Mock(spec=ISessionLoopGuard))
    container.register(IConfigService, instance=Mock(spec=IConfigService))
    container.register(ILlmClient, instance=Mock(spec=ILlmClient))
    container.register(IPromptManager, instance=Mock(spec=IPromptManager))
    container.register(ISystemEnvironment, instance=system_env)
    return container, session_manager, user_interactor


def test_start_without_terminal_exits_without_prompting(capsys):
    system_env = FakeSystemEnvironment(isatty=False)
    container, session_manager, user_interactor = _build_container(system_env, reply="")

    with pytest.raises(typer.Exit) as exc_info:
        handlers.handle_new_session(
            container=container,
            name=None,
            agent="pathfinder",
            require_approval=False,
            no_copy=True,
            message=None,
        )

    assert exc_info.value.exit_code == 1
    user_interactor.ask_question.assert_not_called()
    session_manager.create_session.assert_not_called()
    captured = capsys.readouterr()
    assert "No terminal input provided for initial message." in (
        captured.out + captured.err
    )


def test_start_with_terminal_prompts_and_seeds_session():
    system_env = FakeSystemEnvironment(isatty=True)
    container, session_manager, user_interactor = _build_container(
        system_env, reply="Build a rocket"
    )

    handlers.handle_new_session(
        container=container,
        name=None,
        agent="pathfinder",
        require_approval=False,
        no_copy=True,
        message=None,
    )

    user_interactor.ask_question.assert_called_once_with("What are we working on?")
    session_manager.create_session.assert_called_once()
    options = session_manager.create_session.call_args.args[0]
    assert options.initial_request == "Build a rocket"


def test_start_with_message_never_consults_presence():
    system_env = FakeSystemEnvironment(isatty=False)
    container, session_manager, user_interactor = _build_container(system_env, reply="")

    handlers.handle_new_session(
        container=container,
        name=None,
        agent="pathfinder",
        require_approval=False,
        no_copy=True,
        message="Refactor auth",
    )

    user_interactor.ask_question.assert_not_called()
    session_manager.create_session.assert_called_once()
    options = session_manager.create_session.call_args.args[0]
    assert options.initial_request == "Refactor auth"
