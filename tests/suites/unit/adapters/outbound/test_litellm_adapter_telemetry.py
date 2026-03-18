import pytest
from unittest.mock import MagicMock, patch
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter


@pytest.fixture
def mock_config():
    return MagicMock()


@pytest.fixture
def adapter(mock_config):
    return LiteLLMAdapter(mock_config)


def test_get_token_count_delegates_to_litellm(adapter):
    messages = [{"role": "user", "content": "Hello"}]
    model = "gpt-4"

    with patch("litellm.token_counter") as mock_counter:
        mock_counter.return_value = 10
        count = adapter.get_token_count(model, messages)

        assert count == 10  # noqa: PLR2004
        mock_counter.assert_called_once_with(model=model, messages=messages)


def test_get_completion_cost_delegates_to_litellm(adapter):
    mock_response = MagicMock()

    with patch("litellm.completion_cost") as mock_cost:
        mock_cost.return_value = 0.05
        cost = adapter.get_completion_cost(mock_response)

        assert cost == 0.05  # noqa: PLR2004
        mock_cost.assert_called_once_with(completion_response=mock_response)
