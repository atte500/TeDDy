from typing import Any
import pytest
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.time_service import ITimeService
from tests.harness.setup.mocking import POSIXPathMock, register_mock


def test_litellm_adapter_uses_configured_retries(container: Any) -> None:
    # Arrange
    mock_config = register_mock(container, IConfigService)
    mock_time = register_mock(container, ITimeService)

    # Configure 4 retries
    def mock_get_setting(key: str, default: Any = None) -> Any:
        if key == "llm.max_retries":
            return 4
        if key == "llm":
            return {"max_retries": 4}
        return default

    mock_config.get_setting.side_effect = mock_get_setting

    # Mock litellm.completion to fail with SSL error
    # Use POSIXPathMock directly for internal providers to allow arbitrary attributes
    mock_litellm = POSIXPathMock()
    mock_litellm.completion.side_effect = Exception("SSLV3_ALERT_BAD_RECORD_MAC")

    # Use constructor injection to provide the mocked litellm and time_service
    adapter = LiteLLMAdapter(
        config_service=mock_config,
        time_service=mock_time,
        _litellm_provider=mock_litellm,
    )

    # Act
    with pytest.raises(Exception, match="LLM Completion failed"):
        adapter.get_completion(
            messages=[{"role": "user", "content": "hi"}], model="gpt-4o"
        )

    # Assert
    # 4 attempts expected
    assert mock_litellm.completion.call_count == 4
    # Ensure sleep was called for the first 3 failing attempts
    assert mock_time.sleep.call_count == 3
