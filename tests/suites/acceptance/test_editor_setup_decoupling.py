"""Acceptance test for the editor-setup decoupling (Slice 00-26).

Drives the CLI in-process (Subcutaneous Testing) to prove that a yolo session
which still reads the terminal (no ``-m`` supplied, so the opening-message
prompt will fire) runs the one-time editor setup on a TTY -- even though the
approval flag (``interactive``) is False.
"""

from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def test_start_yolo_without_message_prompts_for_editor_on_tty(tmp_path, monkeypatch):
    """Scenario: yolo (no ``-m``) on a TTY must run the editor setup prompt.

    A ``-y`` run without ``-m`` blocks on the opening-message prompt, so the
    session still reads the terminal and the one-time editor setup must run. This
    is the end-to-end behavioural flip delivered by Slice 00-26: the editor gate
    is keyed on "will the session read the terminal" rather than on the yolo
    approval flag.
    """
    # Arrange: TTY-on, unconfigured editor, deterministic discovery + selection.
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_tty(True)
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    mock_config = env.get_service(IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: (
        "" if key == "editor" else default
    )

    mock_prompt_manager = env.mock_port(IPromptManager)
    mock_prompt_manager.get_prompt_content.return_value = "pathfinder prompt"

    monkeypatch.setattr(
        ConsoleToolingHelper,
        "discover_editors",
        lambda self: [("nvim", "/usr/bin/nvim"), ("vim", "/usr/bin/vim")],
    )
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "1")

    # Act: yolo mode, no -m -> interactive is False, but the terminal is read
    # (the opening-message prompt fires), so editor setup must run.
    result = adapter.run_start(["-y", "--no-copy"])

    # Assert: the editor setup prompt rendered and persisted the selection.
    output = result.stdout + result.stderr
    assert "Editor Setup" in output
    mock_config.set_setting.assert_called_once_with("editor", "nvim")