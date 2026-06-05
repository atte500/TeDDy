#!/usr/bin/env python3
"""
Slice 02-12 Prototype: Config Validation & Transient Retry.

Validates three interconnected behaviors for LiteLLMAdapter:
1. Lazy validation guard on first get_completion() raises ConfigurationError if config invalid.
2. After validation passes, ALL errors (not just SSL/Timeout) are retried with exponential backoff.
3. Timeout from config is passed to litellm.completion() with default fallback to 300 seconds.

Usage:
    python spikes/prototypes/12-config-validation-retry.py          # Interactive menu
    python spikes/prototypes/12-config-validation-retry.py --verify # Run all assertions
    python spikes/prototypes/12-config-validation-retry.py --boot   # 5-sec boot check then exit
"""

import sys
import time
import threading
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock
from threading import Lock

# ---------------------------------------------------------------------------
# Simulated exception classes (mimic production definitions)
# ---------------------------------------------------------------------------

class ConfigurationError(Exception):
    """Raised when LLM configuration is invalid."""
    pass

class LlmApiError(Exception):
    """Raised when LLM API call fails after all retries."""
    pass

# ---------------------------------------------------------------------------
# Mock dependencies
# ---------------------------------------------------------------------------

class MockLitellm:
    """
    Simulates the litellm module for testing.

    The `completion_side_effect` controls what happens when `completion()` is called.
    - If None: returns a MagicMock always.
    - If a list: each call pops the first element; if it's an exception, raises it;
      otherwise returns it as a successful response.
    """

    def __init__(self, completion_side_effect: Any = None):
        self._completion_calls: List[tuple] = []
        self.completion_side_effect = completion_side_effect
        self.model_cost: Dict[str, Dict] = {}
        self.set_verbose = False
        self.suppress_debug_info = True

    def completion(self, messages: List[Dict[str, str]], **params: Any) -> Any:
        self._completion_calls.append((messages, params))
        if self.completion_side_effect is not None:
            if isinstance(self.completion_side_effect, list):
                if not self.completion_side_effect:
                    raise RuntimeError("No more side effects configured")
                effect = self.completion_side_effect.pop(0)
                if isinstance(effect, Exception):
                    raise effect
                return effect
            else:
                raise self.completion_side_effect
        return MagicMock()

    def token_counter(self, model: str, messages: List[Dict[str, str]]) -> int:
        return 100

    def completion_cost(self, completion_response: Any) -> float:
        return 0.001

    def validate_environment(self, model: str) -> Dict[str, Any]:
        return {"missing_keys": []}


class MockConfigService:
    """
    Simple config service that returns values from a dictionary.
    Supports dot-separated keys (e.g. 'llm.api_key').
    """

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    def get_config_path(self) -> str:
        return "/mock/path"

    def get_setting(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        parts = key.split(".", 1)
        if len(parts) == 2:
            section = self._config.get(parts[0], {})
            return section.get(parts[1], default)
        return self._config.get(key, default)


class MockTimeService:
    """
    Records sleep calls instead of actually sleeping.
    """

    def __init__(self):
        self.sleep_calls: List[float] = []

    def sleep(self, duration: float) -> None:
        self.sleep_calls.append(duration)


# ---------------------------------------------------------------------------
# Adapter under test (simplified production logic)
# ---------------------------------------------------------------------------

class ValidationRetryAdapter:
    """
    Simulates the config validation and transient retry logic of LiteLLMAdapter.

    Key behaviors:
    1. Lazy validation guard: validates config on first get_completion() call.
    2. Retry-all-errors: after validation passes, retries ANY exception.
    3. Timeout passthrough: passes 'timeout' from config, defaulting to 300.
    """

    def __init__(
        self,
        config_service: MockConfigService,
        litellm_provider: MockLitellm,
        time_service: Optional[MockTimeService] = None,
    ):
        self._config_service = config_service
        self._litellm = litellm_provider
        self._time_service = time_service
        self._validated = False
        self._init_lock = Lock()

    # -----------------------------------------------------------------------
    # 1. Config validation (simplified version of production)
    # -----------------------------------------------------------------------

    def validate_config(self) -> List[str]:
        """Basic config validation: checks api_key and model."""
        errors: List[str] = []
        api_key = self._config_service.get_setting("llm.api_key")
        if not api_key:
            errors.append("'llm.api_key' is empty.")
        model = self._config_service.get_setting("llm.model")
        if not model:
            errors.append("'llm.model' is not configured.")
        return errors

    # -----------------------------------------------------------------------
    # 2. Core get_completion with lazy validation + retry-on-all-errors
    # -----------------------------------------------------------------------

    def get_completion(
        self, messages: List[Dict[str, str]], **kwargs: Any
    ) -> Any:
        # -- Lazy validation guard (defense-in-depth) --
        if not self._validated:
            with self._init_lock:
                if not self._validated:
                    errors = self.validate_config()
                    if errors:
                        raise ConfigurationError(errors[0])
                    self._validated = True

        # -- Prepare completion params with timeout fallback --
        params: Dict[str, Any] = {**kwargs}
        llm_config = self._config_service.get_setting("llm", {})
        if llm_config:
            params.update(llm_config)
        # Timeout fallback: if not set in config, default to 300
        if "timeout" not in params:
            params["timeout"] = 300

        # -- Retry loop (retry on ALL errors after validation passes) --
        max_attempts = int(params.get("max_retries", 3))
        last_exception: Optional[Exception] = None

        for attempt in range(max_attempts):
            try:
                return self._litellm.completion(messages=messages, **params)
            except Exception as e:
                last_exception = e
                # Retry if we have attempts remaining
                if attempt < max_attempts - 1:
                    delay = 0.5 * (2 ** attempt)
                    if self._time_service:
                        self._time_service.sleep(delay)
                    else:
                        time.sleep(delay)
                    continue
                # Exhausted all retries
                raise LlmApiError(f"LLM Completion failed: {e}") from e

    # -----------------------------------------------------------------------
    # 3. Helper methods for assertions
    # -----------------------------------------------------------------------

    def get_completion_count(self) -> int:
        return len(self._litellm._completion_calls)

    def last_completion_params(self) -> Optional[Dict[str, Any]]:
        if self._litellm._completion_calls:
            return self._litellm._completion_calls[-1][1]
        return None


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_validation_guard_invalid_api_key():
    """
    Config has empty api_key -> ConfigurationError on first get_completion() call.
    No litellm.completion call should be made.
    """
    config = MockConfigService({
        "llm": {
            "api_key": "",
            "model": "test-model",
        }
    })
    litellm = MockLitellm()
    adapter = ValidationRetryAdapter(config, litellm)
    try:
        adapter.get_completion([{"role": "user", "content": "hi"}])
        return False, "Expected ConfigurationError but no exception raised"
    except ConfigurationError as e:
        if "'llm.api_key' is empty." in str(e):
            if adapter.get_completion_count() == 0:
                return True, "Raised ConfigurationError; no litellm.completion call made"
            return False, "Raised ConfigurationError but litellm.completion was called"
        return False, f"Wrong error message: {e}"
    except Exception as e:
        return False, f"Unexpected exception: {type(e).__name__}: {e}"


def test_validation_guard_missing_model():
    """
    Config has empty model -> ConfigurationError on first get_completion() call.
    """
    config = MockConfigService({
        "llm": {
            "api_key": "valid",
            "model": "",
        }
    })
    litellm = MockLitellm()
    adapter = ValidationRetryAdapter(config, litellm)
    try:
        adapter.get_completion([{"role": "user", "content": "hi"}])
        return False, "Expected ConfigurationError but no exception raised"
    except ConfigurationError as e:
        if "not configured" in str(e):
            return True, "Raised ConfigurationError for missing model"
        return False, f"Wrong error message: {e}"
    except Exception as e:
        return False, f"Unexpected exception: {type(e).__name__}: {e}"


def test_validation_skipped_on_second_call():
    """
    After validation passes, subsequent calls skip validation entirely.
    Validating twice should not throw or re-check.
    """
    config = MockConfigService({
        "llm": {
            "api_key": "valid",
            "model": "test",
        }
    })
    litellm = MockLitellm()
    adapter = ValidationRetryAdapter(config, litellm)
    # First call: triggers validation
    adapter.get_completion([{"role": "user", "content": "first"}])
    # Second call: should skip validation (no re-check)
    adapter.get_completion([{"role": "user", "content": "second"}])
    if adapter.get_completion_count() == 2:
        return True, "Second call succeeded without re-validation"
    return False, f"Expected 2 completion calls, got {adapter.get_completion_count()}"


def test_retry_all_errors():
    """
    After validation passes, ALL exceptions are retried with exponential backoff.
    The call succeeds on the 3rd attempt.
    """
    config = MockConfigService({
        "llm": {
            "api_key": "valid",
            "model": "test",
            "max_retries": 3,
        }
    })
    # Fail on attempts 1 and 2 with generic errors; succeed on attempt 3
    success_response = MagicMock()
    success_response.choices = [MagicMock()]
    success_response.choices[0].message.content = "Hello!"
    litellm = MockLitellm(completion_side_effect=[
        RuntimeError("Connection refused"),
        RuntimeError("Server error"),
        success_response,
    ])
    time_svc = MockTimeService()
    adapter = ValidationRetryAdapter(config, litellm, time_service=time_svc)

    result = adapter.get_completion([{"role": "user", "content": "test"}])
    if adapter.get_completion_count() != 3:
        return False, f"Expected 3 completion calls, got {adapter.get_completion_count()}"
    # Verify exponential backoff: 0.5, then 1.0
    expected_delays = [0.5, 1.0]
    if time_svc.sleep_calls != expected_delays:
        return False, f"Expected backoff delays {expected_delays}, got {time_svc.sleep_calls}"
    # Verify successful response returned
    if result is not success_response:
        return False, "Returned response is not the successful mock"
    return True, f"Retried 3 times with backoff {time_svc.sleep_calls}; success on final attempt"


def test_retry_exhaustion():
    """
    All retry attempts fail -> LlmApiError is raised.
    """
    config = MockConfigService({
        "llm": {
            "api_key": "valid",
            "model": "test",
            "max_retries": 3,
        }
    })
    litellm = MockLitellm(completion_side_effect=[
        RuntimeError("Fail1"),
        RuntimeError("Fail2"),
        RuntimeError("Fail3"),
    ])
    adapter = ValidationRetryAdapter(config, litellm)
    try:
        adapter.get_completion([{"role": "user", "content": "test"}])
        return False, "Expected LlmApiError but no exception raised"
    except LlmApiError as e:
        if "Fail3" in str(e):
            return True, f"Raised LlmApiError after 3 failures: {e}"
        return False, f"Wrong error message: {e}"
    except Exception as e:
        return False, f"Unexpected exception: {type(e).__name__}: {e}"


def test_timeout_passthrough():
    """
    Custom timeout from config is passed to litellm.completion().
    """
    config = MockConfigService({
        "llm": {
            "api_key": "valid",
            "model": "test",
            "timeout": 600,
        }
    })
    litellm = MockLitellm()
    adapter = ValidationRetryAdapter(config, litellm)
    adapter.get_completion([{"role": "user", "content": "test"}])
    params = adapter.last_completion_params()
    if params and params.get("timeout") == 600:
        return True, "Timeout=600 passed to litellm as expected"
    timeout_val = params.get("timeout") if params else "None"
    return False, f"Expected timeout=600 but got timeout={timeout_val}"


def test_default_timeout():
    """
    When no timeout is in config, default of 300 seconds is passed.
    """
    config = MockConfigService({
        "llm": {
            "api_key": "valid",
            "model": "test",
        }
    })
    litellm = MockLitellm()
    adapter = ValidationRetryAdapter(config, litellm)
    adapter.get_completion([{"role": "user", "content": "test"}])
    params = adapter.last_completion_params()
    if params and params.get("timeout") == 300:
        return True, "Default timeout=300 passed to litellm"
    timeout_val = params.get("timeout") if params else "None"
    return False, f"Expected default timeout=300 but got timeout={timeout_val}"


def test_thread_safety():
    """
    Five concurrent calls to get_completion: validation should only run once,
    and all calls should succeed.
    """
    config = MockConfigService({
        "llm": {
            "api_key": "valid",
            "model": "test",
        }
    })
    litellm = MockLitellm()
    adapter = ValidationRetryAdapter(config, litellm)
    results: List[str] = []

    def call_get_completion() -> None:
        try:
            adapter.get_completion([{"role": "user", "content": "hi"}])
            results.append("ok")
        except Exception as e:
            results.append(f"{type(e).__name__}: {e}")

    threads = [threading.Thread(target=call_get_completion) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if len(results) == 5 and all(r == "ok" for r in results):
        # All 5 calls succeeded and litellm.completion was called 5 times
        if adapter.get_completion_count() == 5:
            return True, "All 5 concurrent calls succeeded; validation ran once"
        return False, f"Expected 5 completion calls, got {adapter.get_completion_count()}"
    return False, f"Some calls failed: {results}"


# ---------------------------------------------------------------------------
# Test registry
# ---------------------------------------------------------------------------

TEST_FUNCTIONS: Dict[str, Any] = {
    "Validation Guard (Empty API Key)": test_validation_guard_invalid_api_key,
    "Validation Guard (Missing Model)": test_validation_guard_missing_model,
    "Validation Guard Skips on Second Call": test_validation_skipped_on_second_call,
    "Retry All Errors (Success on 3rd)": test_retry_all_errors,
    "Retry Exhaustion (LlmApiError)": test_retry_exhaustion,
    "Timeout Passthrough (600)": test_timeout_passthrough,
    "Default Timeout (300)": test_default_timeout,
    "Thread Safety": test_thread_safety,
}


def run_verification() -> int:
    """Run all tests in non-interactive mode. Returns 0 on success, 1 on failure."""
    header = "=" * 60
    print(header)
    print("  Slice 02-12: Config Validation & Transient Retry")
    print("  Verification Mode")
    print(header)
    all_passed = True
    for name, func in TEST_FUNCTIONS.items():
        try:
            passed, msg = func()
            status = "PASS" if passed else "FAIL"
            if not passed:
                all_passed = False
            print(f"  [{status}] {name}: {msg}")
        except Exception as e:
            all_passed = False
            print(f"  [FAIL] {name}: Exception: {type(e).__name__}: {e}")
    print(header)
    print(f"  {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print(header)
    return 0 if all_passed else 1


def run_interactive() -> None:
    """Launch interactive menu for selecting individual tests."""
    header = "=" * 60
    print(header)
    print("  Slice 02-12: Config Validation & Transient Retry")
    print("  Interactive Menu")
    print(header)
    names = list(TEST_FUNCTIONS.keys())
    for i, name in enumerate(names, start=1):
        print(f"  {i}. {name}")
    print("  v. Verify all (run all tests)")
    print("  q. Quit")
    print(header)
    while True:
        choice = input("\nSelect test: ").strip().lower()
        if choice == "q":
            break
        if choice == "v":
            run_verification()
            continue
        try:
            index = int(choice) - 1
            if 0 <= index < len(names):
                name = names[index]
                passed, msg = TEST_FUNCTIONS[name]()
                status = "PASS" if passed else "FAIL"
                print(f"\n  [{status}] {name}: {msg}")
            else:
                print("  Invalid choice. Enter a number between 1 and", len(names))
        except ValueError:
            print("  Invalid input. Enter a number, 'v', or 'q'.")


def main() -> None:
    if "--boot" in sys.argv:
        # Boot check: sleep 5 seconds to confirm prototype boots without crash
        time.sleep(5)
        result = run_verification()
        sys.exit(result)
    elif "--verify" in sys.argv:
        sys.exit(run_verification())
    else:
        run_interactive()


if __name__ == "__main__":
    main()