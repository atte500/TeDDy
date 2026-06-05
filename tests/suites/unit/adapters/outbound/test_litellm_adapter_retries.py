from typing import Any, Dict, List, Optional
import threading
import pytest
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.core.domain.models.exceptions import ConfigurationError
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.time_service import ITimeService
from tests.harness.setup.mocking import POSIXPathMock, register_mock


# ---------------------------------------------------------------------------
# Helper: create a mock_config with a controllable get_setting side_effect
# that returns valid llm config by default
# ---------------------------------------------------------------------------


def _valid_llm_config() -> Dict[str, Any]:
    """Returns a valid llm config dict for testing."""
    return {
        "llm": {
            "api_key": "sk-test-key",  # pragma: allowlist secret
            "model": "openrouter/test-model",
            "max_retries": 3,
        },
    }


def _create_valid_config_mock(
    container: Any, overrides: Optional[Dict[str, Any]] = None
) -> Any:
    """Creates a mock IConfigService with controllable get_setting."""
    mock_config = register_mock(container, IConfigService)
    config = _valid_llm_config()
    if overrides:
        config["llm"].update(overrides)

    def mock_get_setting(key: str, default: Any = None) -> Any:
        parts = key.split(".", 1)
        if len(parts) == 2:
            section = config.get(parts[0].lower(), {})
            return section.get(parts[1], default)
        return config.get(key, default)
        if key == "llm.max_retries":
            return 4
        if key == "llm":
            return {"max_retries": 4, "api_key": "sk-test-key", "model": "gpt-4o"}
        if key == "llm.api_key":
            return "sk-test-key"  # pragma: allowlist secret
        if key == "llm.model":
            return "gpt-4o"
        return default

    mock_config.get_setting.side_effect = mock_get_setting
    return mock_config


def _create_adapter(
    container: Any, config_overrides: Optional[Dict[str, Any]] = None
) -> tuple[LiteLLMAdapter, Any, Any]:
    """Creates a fully mocked LiteLLMAdapter and returns (adapter, mock_litellm, mock_time)."""
    mock_config = _create_valid_config_mock(container, config_overrides)
    mock_time = register_mock(container, ITimeService)
    mock_litellm = POSIXPathMock()

    # Record sleep calls for backoff verification
    mock_time.sleep_calls = []

    def _track_sleep(duration: float) -> None:
        mock_time.sleep_calls.append(duration)

    mock_time.sleep.side_effect = _track_sleep

    adapter = LiteLLMAdapter(
        config_service=mock_config,
        time_service=mock_time,
        _litellm_provider=mock_litellm,
    )
    return adapter, mock_litellm, mock_time


# =========== Test 1: Lazy Validation Guard ===========


def test_validation_guard_blocks_invalid_api_key(container: Any) -> None:
    """
    Given invalid config (empty API key),
    When get_completion is called for the first time,
    Then a ConfigurationError must be raised and NO litellm call made.
    """
    # Arrange: Empty API key triggers validate_config to return errors
    mock_config = register_mock(container, IConfigService)
    mock_config.get_setting.side_effect = lambda key, default=None: {
        "llm.api_key": "",
        "llm.model": "openrouter/test-model",
    }.get(key, default)

    mock_litellm = POSIXPathMock()
    mock_litellm.completion.side_effect = Exception("Should not be called")

    adapter = LiteLLMAdapter(
        config_service=mock_config,
        _litellm_provider=mock_litellm,
    )

    # Act / Assert
    with pytest.raises(ConfigurationError, match="'llm.api_key' is empty"):
        adapter.get_completion(messages=[{"role": "user", "content": "hi"}])

    # Assert: No litellm.completion call was made
    assert mock_litellm.completion.call_count == 0, (
        f"Expected 0 litellm calls but got {mock_litellm.completion.call_count}"
    )


def test_validation_guard_allows_valid_config(container: Any) -> None:
    """
    Given valid config,
    When get_completion is called,
    Then the call proceeds to litellm (no ConfigurationError raised).
    """
    # Arrange: Valid config
    adapter, mock_litellm, _ = _create_adapter(container)

    # Act
    adapter.get_completion(messages=[{"role": "user", "content": "hi"}])

    # Assert: litellm was called
    assert mock_litellm.completion.call_count == 1, (
        f"Expected 1 litellm call but got {mock_litellm.completion.call_count}"
    )


def test_validation_guard_skipped_on_subsequent_calls(container: Any) -> None:
    """
    After validation passes on the first call, subsequent calls skip validation.
    """
    # Arrange
    adapter, mock_litellm, _ = _create_adapter(container)

    # Act: Two successful calls
    adapter.get_completion(messages=[{"role": "user", "content": "first"}])
    adapter.get_completion(messages=[{"role": "user", "content": "second"}])

    # Assert: Two completion calls made
    assert mock_litellm.completion.call_count == 2


# =========== Test 2: Retry-All-Errors ===========


def test_retry_all_errors_with_exponential_backoff(container: Any) -> None:
    """
    After validation passes, generic RuntimeError on attempts 1-2 should be retried.
    Attempt 3 succeeds. Verify exponential backoff [0.5s, 1.0s].
    """
    # Arrange: Valid config with 3 retries
    adapter, mock_litellm, mock_time = _create_adapter(container)

    # Fail on attempts 1 and 2 with generic errors; succeed on attempt 3
    success_response = POSIXPathMock()
    success_response.choices = [POSIXPathMock()]
    success_response.choices[0].message.content = "Hello!"

    mock_litellm.completion.side_effect = [
        RuntimeError("Connection refused"),  # Attempt 1
        RuntimeError("Server error"),  # Attempt 2
        success_response,  # Attempt 3 (success)
    ]

    # Act
    result = adapter.get_completion(messages=[{"role": "user", "content": "test"}])

    # Assert
    assert mock_litellm.completion.call_count == 3, (
        f"Expected 3 litellm calls but got {mock_litellm.completion.call_count}"
    )
    # Exponential backoff: 0.5 * 2^0 = 0.5, 0.5 * 2^1 = 1.0
    expected_delays = [0.5, 1.0]
    assert mock_time.sleep_calls == expected_delays, (
        f"Expected backoff delays {expected_delays} but got {mock_time.sleep_calls}"
    )
    # Verify successful response returned
    assert result is success_response, "Returned response is not the successful mock"


def test_retry_exhaustion_raises_llm_api_error(container: Any) -> None:
    """
    All 3 attempts fail with generic errors -> LlmApiError raised.
    """
    # Arrange
    adapter, mock_litellm, mock_time = _create_adapter(container)

    mock_litellm.completion.side_effect = [
        RuntimeError("Fail1"),
        RuntimeError("Fail2"),
        RuntimeError("Fail3"),
    ]

    # Act / Assert
    with pytest.raises(Exception, match="LLM Completion failed") as exc_info:
        adapter.get_completion(messages=[{"role": "user", "content": "test"}])

    # Verify it's LlmApiError (not ConfigurationError or generic Exception)
    from teddy_executor.core.ports.outbound.llm_client import LlmApiError

    assert isinstance(exc_info.value, LlmApiError), (
        f"Expected LlmApiError but got {type(exc_info.value).__name__}"
    )
    assert mock_litellm.completion.call_count == 3


# =========== Test 3: Thread Safety ===========


def test_thread_safety_concurrent_calls(container: Any) -> None:
    """
    Five concurrent calls to get_completion: all should succeed,
    validation runs exactly once, litellm called 5 times.
    """
    # Arrange
    adapter, mock_litellm, _ = _create_adapter(container)
    results: List[str] = []
    lock = threading.Lock()

    def call_get_completion() -> None:
        try:
            adapter.get_completion(messages=[{"role": "user", "content": "hi"}])
            with lock:
                results.append("ok")
        except Exception as e:
            with lock:
                results.append(f"{type(e).__name__}: {e}")

    threads = [threading.Thread(target=call_get_completion) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 5, f"Expected 5 results but got {len(results)}"
    assert all(r == "ok" for r in results), f"Some calls failed: {results}"
    assert mock_litellm.completion.call_count == 5, (
        f"Expected 5 litellm calls but got {mock_litellm.completion.call_count}"
    )


# =========== Test 4: Timeout Passthrough ===========


def test_custom_timeout_from_config_passed_to_litellm(container: Any) -> None:
    """
    Given a config with timeout=600,
    When get_completion is called,
    Then litellm receives timeout=600 in its kwargs.
    """
    # Arrange: Override timeout to 600
    adapter, mock_litellm, _ = _create_adapter(container, {"timeout": 600})

    # Act
    adapter.get_completion(messages=[{"role": "user", "content": "test"}])

    # Assert
    call_kwargs = mock_litellm.completion.call_args.kwargs
    assert call_kwargs.get("timeout") == 600, (
        f"Expected timeout=600 but got timeout={call_kwargs.get('timeout')}"
    )


def _create_adapter_no_timeout(container: Any) -> tuple[LiteLLMAdapter, Any, Any]:
    """Creates an adapter with a valid llm config that has NO 'timeout' key."""
    from teddy_executor.core.ports.outbound.config_service import IConfigService

    config = {
        "llm": {
            "api_key": "sk-test-key",  # pragma: allowlist secret
            "model": "openrouter/test-model",
            "max_retries": 3,
        },
    }
    mock_config = register_mock(container, IConfigService)

    def mock_get_setting(key: str, default: Any = None) -> Any:
        parts = key.split(".", 1)
        if len(parts) == 2:
            section = config.get(parts[0].lower(), {})
            return section.get(parts[1], default)
        return config.get(key, default)

    mock_config.get_setting.side_effect = mock_get_setting

    mock_time = register_mock(container, ITimeService)
    mock_litellm = POSIXPathMock()
    mock_time.sleep_calls = []

    def _track_sleep(duration: float) -> None:
        mock_time.sleep_calls.append(duration)

    mock_time.sleep.side_effect = _track_sleep

    adapter = LiteLLMAdapter(
        config_service=mock_config,
        time_service=mock_time,
        _litellm_provider=mock_litellm,
    )
    return adapter, mock_litellm, mock_time


def test_default_timeout_is_300_when_not_configured(container: Any) -> None:
    """
    When the llm config does not contain a 'timeout' key,
    the adapter should default to timeout=300 seconds.
    """
    # Arrange: Config without timeout
    adapter, mock_litellm, _ = _create_adapter_no_timeout(container)

    # Act
    adapter.get_completion(messages=[{"role": "user", "content": "test"}])

    # Assert
    call_kwargs = mock_litellm.completion.call_args.kwargs
    assert call_kwargs.get("timeout") == 300, (
        f"Expected default timeout=300 but got timeout={call_kwargs.get('timeout')}"
    )


def test_timeout_exception_triggers_retry(container: Any) -> None:
    """
    Given a config without timeout,
    When litellm raises a TimeoutError on the first attempt,
    Then the adapter retries and succeeds on the second attempt.
    """
    # Arrange: Config without timeout
    adapter, mock_litellm, mock_time = _create_adapter_no_timeout(container)

    # Simulate: attempt 1 fails with TimeoutError, attempt 2 succeeds
    success_response = POSIXPathMock()
    success_response.choices = [POSIXPathMock()]
    success_response.choices[0].message.content = "Hello!"
    mock_litellm.completion.side_effect = [
        TimeoutError("Request timed out"),  # Attempt 1
        success_response,  # Attempt 2 (success)
    ]

    # Act
    result = adapter.get_completion(messages=[{"role": "user", "content": "test"}])

    # Assert
    assert mock_litellm.completion.call_count == 2, (
        f"Expected 2 litellm calls but got {mock_litellm.completion.call_count}"
    )
    # Verify backoff delay
    assert mock_time.sleep_calls == [0.5], (
        f"Expected backoff delay [0.5] but got {mock_time.sleep_calls}"
    )
    assert result is success_response, "Returned response is not the successful mock"
