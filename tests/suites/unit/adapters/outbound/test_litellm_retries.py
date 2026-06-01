import pytest
import litellm
from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.core.ports.outbound.llm_client import LlmApiError
from teddy_executor.core.ports.outbound.config_service import IConfigService


def test_litellm_adapter_retries_on_ssl_error(monkeypatch):
    """
    Test that the adapter retries the completion call on specific SSL errors.
    """
    # Arrange
    config_service = POSIXPathMock(spec=IConfigService)
    config_service.get_setting.return_value = {"model": "gpt-4o"}

    adapter = LiteLLMAdapter(config_service=config_service)

    # Setup the success response using POSIXPathMock for external library consistency
    mock_response = POSIXPathMock()
    mock_choice = POSIXPathMock()
    mock_choice.message.content = "Success"
    mock_response.choices = [mock_choice]

    # Track calls manually since we are using monkeypatch
    call_count = 0
    error_msg = "SSLV3_ALERT_BAD_RECORD_MAC"

    def mock_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception(error_msg)
        return mock_response

    monkeypatch.setattr(litellm, "completion", mock_completion)

    # Act
    result = adapter.get_completion(
        messages=[{"role": "user", "content": "hello"}], model="gpt-4o"
    )

    # Assert
    assert result == mock_response
    assert result.choices[0].message.content == "Success"
    assert call_count == 3


def test_litellm_adapter_exhausts_retries(monkeypatch):
    """
    Test that the adapter eventually raises LlmApiError if all retries fail.
    """
    # Arrange
    config_service = POSIXPathMock(spec=IConfigService)
    config_service.get_setting.return_value = {"model": "gpt-4o"}
    adapter = LiteLLMAdapter(config_service=config_service)

    call_count = 0
    error_msg = "SSLV3_ALERT_BAD_RECORD_MAC"

    def mock_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        raise Exception(error_msg)

    monkeypatch.setattr(litellm, "completion", mock_completion)

    # Act / Assert
    with pytest.raises(LlmApiError) as excinfo:
        adapter.get_completion(
            messages=[{"role": "user", "content": "hello"}], model="gpt-4o"
        )

    assert "LLM Completion failed" in str(excinfo.value)
    # The current implementation will fail on first call, so call_count will be 1.
    # After implementation, it should be 3.
    assert call_count == 3
