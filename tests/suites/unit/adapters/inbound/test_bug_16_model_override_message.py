"""Regression test for Bug #16: Model override ignored in config success message.

The bug: `_echo_config_success` reads model from config_service.get_setting()
instead of accepting an optional `model` parameter from the CLI.
This test verifies the fix by passing a model override and asserting it appears
in the output.
"""

from io import StringIO
import typer

from teddy_executor.adapters.inbound.session_cli_handlers import _echo_config_success
from teddy_executor.core.ports.outbound.config_service import IConfigService


def test_echo_config_success_with_model_override(env):
    """Verify _echo_config_success displays the override model when provided."""
    config_service = env.mock_port(IConfigService)
    config_service.get_setting.return_value = (
        "openrouter/deepseek/deepseek-v4-flash:nitro"
    )
    container = env.container

    captured = StringIO()
    original_echo = typer.echo

    def _echo(msg: str, err: bool = True) -> None:
        captured.write(msg + "\n")

    typer.echo = _echo  # type: ignore[assignment]

    try:
        override_model = "openrouter/deepseek/deepseek-v4-pro:nitro"
        _echo_config_success(container, agent="pathfinder", model=override_model)
    finally:
        typer.echo = original_echo

    output = captured.getvalue()
    assert override_model in output, (
        f"Expected override model '{override_model}' in output, got: {output.strip()}"
    )
    assert "deepseek-v4-flash" not in output, (
        "Config model 'deepseek-v4-flash' should not appear when override is provided."
    )
    assert "pathfinder" in output
