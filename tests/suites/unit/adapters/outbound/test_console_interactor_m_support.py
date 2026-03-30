from unittest.mock import MagicMock, patch
from teddy_executor.adapters.outbound.console_interactor import ConsoleInteractorAdapter
from teddy_executor.core.domain.models.plan import ActionData


def test_confirm_action_supports_m_for_message(monkeypatch):
    # Ensure no environment pollution affects this test
    monkeypatch.delenv("TEDDY_TEST_MOCK_EDITOR_OUTPUT", raising=False)

    # Setup
    mock_env = MagicMock()
    # Mock system_env to avoid real IO
    mock_env.create_temp_file.return_value = "/tmp/fake.md"
    mock_env.get_env.return_value = "nano"

    interactor = ConsoleInteractorAdapter(mock_env)
    action = ActionData(type="EXECUTE", params={}, description="test")

    # Mock typer.prompt to simulate user entering 'm' then 'y'
    # First prompt: 'm' (to add message)
    # Second prompt: 'y' (to approve after message added)
    prompts = iter(["m", "y"])
    monkeypatch.setattr("typer.prompt", lambda p, **_: next(prompts))

    # Mock editor content reading
    # We need to mock 'open' to simulate reading the message from the temp file
    mock_open = MagicMock()
    mock_open.return_value.__enter__.return_value.read.return_value = (
        "New user instruction"
    )

    with patch("builtins.open", mock_open):
        approved, message = interactor.confirm_action(action, "Approve?")

    # Assertions
    # This should fail initially because 'm' is not handled
    assert approved is True
    assert message == "New user instruction"
