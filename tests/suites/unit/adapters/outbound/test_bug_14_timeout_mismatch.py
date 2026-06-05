"""
Regression test for Bug #14: CI fails because test_get_completion_calls_litellm_correctly
does not account for the default timeout=300 injected by _prepare_completion_params.

Run with: pytest tests/suites/unit/adapters/outbound/test_bug_14_timeout_mismatch.py -v
"""

from unittest.mock import Mock
import litellm

from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter


def test_timeout_param_included_in_completion_call(mock_config):
    """
    Verifies that get_completion passes timeout=300 to litellm.completion
    when no explicit timeout is provided.
    """
    # Arrange
    mock_response = Mock()
    mock_choice = Mock()
    mock_choice.message.content = "AI response text"
    mock_response.choices = [mock_choice]
    litellm.completion.return_value = mock_response

    config = {
        "api_key": "sk-test",  # pragma: allowlist secret
        "model": "test-model",
        "max_retries": 3,
    }  # pragma: allowlist secret

    def _valid_llm(key: str, default=None):
        return (
            config.get(key.split(".", 1)[1] if "." in key else key, default)
            if key.startswith("llm")
            else default
        )

    mock_config.get_setting.side_effect = _valid_llm

    adapter = LiteLLMAdapter(mock_config)
    messages = [{"role": "user", "content": "Hello"}]
    model = "gpt-4"

    # Act
    result = adapter.get_completion(model=model, messages=messages, temperature=0.7)

    # Assert
    assert result.choices[0].message.content == "AI response text"
    # This assertion MUST include timeout=300 to match the actual call.
    litellm.completion.assert_called_once_with(
        model=model, messages=messages, temperature=0.7, timeout=300
    )
