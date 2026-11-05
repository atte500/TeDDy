"""Drive handle_new_session with a fake ISystemEnvironment and a closed stdin.

Answers three questions empirically: does the opening prompt reach the ask
loop, which component terminates the run, and does the ask loop honour the
injected presence port?
"""
from __future__ import annotations

import contextlib
import io
import json
import signal
import sys
import tempfile
import time
from typing import Optional

import punq

import teddy_executor.adapters.inbound.session_cli_handlers as handlers
from teddy_executor.adapters.outbound import console_interactor_ask_loop
from teddy_executor.adapters.outbound.console_interactor import (
    ConsoleInteractorAdapter,
)
from teddy_executor.adapters.outbound.console_interactor_ask_loop import (
    ConsoleAskLoop,
)
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor


class FakeSystemEnvironment:
    def __init__(self, isatty_value: bool = False) -> None:
        self._isatty = isatty_value
        self.isatty_calls = 0

    def which(self, command: str) -> Optional[str]:
        return None

    def get_env(self, key: str) -> Optional[str]:
        return None

    def run_command(self, args, check=True, background=False) -> None:
        return None

    def create_temp_file(self, suffix: str = "", mode: str = "w") -> str:
        handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        handle.close()
        return handle.name

    def delete_file(self, path: str) -> None:
        return None

    def isatty(self) -> bool:
        self.isatty_calls += 1
        return self._isatty


class FakeConfigService:
    def get_setting(self, key, default=None):
        values = {"llm.model": "fake/model", "llm.api_key": "fake-key"}
        return values.get(key, default)

    def get_config_path(self) -> str:
        return "/tmp/teddy-probe/.teddy/config.yaml"


class FakeInitUseCase:
    def ensure_initialized(self) -> str:
        return "probe"


class FakeLlmClient:
    def validate_config(self, include_remote: bool = True) -> list[str]:
        return []


class FakePromptManager:
    def get_prompt_content(self, agent_name: str) -> str:
        return "# Probe"

    def get_available_agents(self) -> list[str]:
        return ["pathfinder"]


class FakeSessionManager:
    def get_latest_turn(self, session_name: str) -> str:
        return ""

    def get_cumulative_cost(self, session_name: str) -> float:
        return 0.0


def build_container(system_env, config_service, interactor) -> punq.Container:
    container = punq.Container()
    container.register(
        ISystemEnvironment, factory=lambda: system_env, scope=punq.Scope.singleton
    )
    container.register(
        IConfigService, factory=lambda: config_service, scope=punq.Scope.singleton
    )
    container.register(IInitUseCase, factory=FakeInitUseCase, scope=punq.Scope.singleton)
    container.register(ILlmClient, factory=FakeLlmClient, scope=punq.Scope.singleton)
    container.register(
        IPromptManager, factory=FakePromptManager, scope=punq.Scope.singleton
    )
    container.register(
        IUserInteractor, factory=lambda: interactor, scope=punq.Scope.singleton
    )
    container.register(
        ISessionManager, factory=FakeSessionManager, scope=punq.Scope.singleton
    )
    return container


def install_watchdog(seconds: int):
    def _raise(signum, frame):
        raise TimeoutError(f"probe blocked for more than {seconds}s")

    previous = signal.signal(signal.SIGALRM, _raise)
    signal.alarm(seconds)
    return previous


def main() -> None:
    system_env = FakeSystemEnvironment(isatty_value=False)
    config_service = FakeConfigService()
    interactor = ConsoleInteractorAdapter(system_env, config_service)
    container = build_container(system_env, config_service, interactor)

    handlers._start_background_update_check = lambda: None
    handlers._run_startup_preamble = lambda *args, **kwargs: None
    # The ask loop only scopes terminal ownership around run(); that scope is
    # not part of the presence decision and an in-memory stdin has no file
    # descriptor, so it is neutralised for the probe.
    console_interactor_ask_loop.stdin_owned = contextlib.nullcontext

    loop = interactor._ask_loop
    prompt_calls: list[dict] = []
    original_pt_prompt = loop._pt_prompt

    def recording_pt_prompt(prompt_text: str) -> str:
        value = original_pt_prompt(prompt_text)
        prompt_calls.append({"prompt": prompt_text, "returned": value})
        return value

    loop._pt_prompt = recording_pt_prompt

    original_stdin = sys.stdin
    sys.stdin = io.StringIO("")
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    previous_alarm = install_watchdog(30)
    started = time.monotonic()
    outcome = "returned"
    raised = None
    exit_code = None
    try:
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(
            stderr_buffer
        ):
            handlers.handle_new_session(
                container=container,
                name=None,
                agent="pathfinder",
                require_approval=True,
                no_copy=True,
                message=None,
                pipeline=False,
            )
    except BaseException as error:  # noqa: BLE001 - the probe records termination
        outcome = "raised"
        raised = type(error).__name__
        exit_code = getattr(error, "exit_code", None)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_alarm)
        sys.stdin = original_stdin
    elapsed = time.monotonic() - started

    divergence = {}
    probe_loop = ConsoleAskLoop(
        FakeSystemEnvironment(isatty_value=False), interactor._tooling
    )
    sys.stdin = io.StringIO("")
    divergence["env_false__pipe_stdin__loop_is_tty"] = probe_loop._is_tty()

    class TtyStringIO(io.StringIO):
        def isatty(self) -> bool:
            return True

    sys.stdin = TtyStringIO("")
    divergence["env_false__tty_stdin__loop_is_tty"] = probe_loop._is_tty()
    sys.stdin = original_stdin

    print(
        json.dumps(
            {
                "elapsed_seconds": round(elapsed, 3),
                "outcome": outcome,
                "raised": raised,
                "exit_code": exit_code,
                "system_env_isatty_calls": system_env.isatty_calls,
                "ask_loop_prompt_calls": prompt_calls,
                "reached_interactor_header": "MESSAGE from TeDDy"
                in stderr_buffer.getvalue(),
                "stdout": stdout_buffer.getvalue()[-1200:],
                "stderr": stderr_buffer.getvalue()[-2000:],
                "ask_loop_port_divergence": divergence,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
