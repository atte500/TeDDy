"""Acceptance: the --max-turns / --max-cost flags bound a non-interactive run.

Drives the real CLI boundary with the production loop guard registered, so the
threaded CLI limit is the only thing that can stop the session.
"""

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def _setup_minimal_project(tmp_path) -> None:
    """Create the minimal project files the start path requires."""
    (tmp_path / ".git").mkdir(exist_ok=True)
    prompt_dir = tmp_path / ".teddy" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "pathfinder.xml").write_text(
        "<prompt>Pathfinder Instructions</prompt>", encoding="utf-8"
    )
    (tmp_path / ".teddy" / "init.context").write_text("README.md", encoding="utf-8")
    (tmp_path / "README.md").write_text("Context file content", encoding="utf-8")


def _register_production_guard(env: TestEnvironment) -> None:
    """Swap the harness guard mock for the production guard.

    ``TestEnvironment`` registers ``ISessionLoopGuard`` as an instance mock and
    never resolves it during setup. A later class registration therefore wins,
    so the CLI's ``resolve()`` constructs the production guard with the threaded
    CLI limits.
    """
    import punq

    from teddy_executor.core.ports.outbound.session_loop_guard import (
        ISessionLoopGuard,
    )
    from teddy_executor.core.services.session_loop_guard import (
        ProductionSessionLoopGuard,
    )

    env.container.register(
        ISessionLoopGuard, ProductionSessionLoopGuard, scope=punq.Scope.transient
    )


def test_max_turns_flag_stops_a_non_interactive_run(tmp_path, monkeypatch):
    """Scenario: --max-turns 1 stops the run after one turn.

    Given a non-interactive run reaches the configured turn limit
    When the loop guard evaluates the next turn
    Then the session terminates with a message that names the limit.
    """
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    _setup_minimal_project(tmp_path)
    _register_production_guard(env)

    result = adapter.run_start(["-y", "--max-turns", "1", "-m", "list the files"])

    combined = result.stdout + (result.stderr or "")
    assert result.exit_code == 0, combined
    assert "1/1" in combined, combined
