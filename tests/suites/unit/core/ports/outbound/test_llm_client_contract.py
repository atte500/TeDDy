import pytest
from teddy_executor.core.ports.outbound.llm_client import ILlmClient


def test_llm_client_requires_validate_config():
    """
    Asserts that any implementation of ILlmClient must implement validate_config.
    """

    class MockLlmClient(ILlmClient):
        def get_completion(self, messages, model=None, **kwargs):
            return "ok"

        def get_token_count(self, messages, model=None):
            return 0

        def get_completion_cost(self, _response):
            return 0.0

        def get_context_window(self, model=None):
            return 0

    # Act / Assert
    # This should fail initially because validate_config is not yet
    # an abstract method in the interface (so no TypeError yet),
    # OR it will fail once I add it to the interface but not the mock.
    with pytest.raises(
        TypeError, match="Can't instantiate abstract class MockLlmClient"
    ):
        MockLlmClient()


def test_llm_client_requires_supports_pricing():
    """
    Asserts that any implementation of ILlmClient must implement supports_pricing.
    """

    class IncompleteClient(ILlmClient):
        def get_completion(self, messages, model=None, **kwargs):
            pass

        def get_token_count(self, messages, model=None):
            return 0

        def get_completion_cost(self, _response):
            return 0.0

        def validate_config(self, _include_remote=False):
            return []

        def get_context_window(self, model=None):
            return 0

    # Act / Assert
    with pytest.raises(
        TypeError, match="Can't instantiate abstract class IncompleteClient"
    ):
        IncompleteClient()


def test_llm_client_requires_get_context_window():
    """
    Contraction Phase: Assert that any implementation of ILlmClient must implement get_context_window.
    """

    class MinimalClient(ILlmClient):
        def get_completion(self, messages, model=None, **kwargs):
            pass

        def get_token_count(self, messages, model=None):
            return 0

        def get_completion_cost(self, _response):
            return 0.0

        def validate_config(self, _include_remote=False):
            return []

    # Act / Assert
    with pytest.raises(
        TypeError, match="Can't instantiate abstract class MinimalClient"
    ):
        MinimalClient()


def test_llm_client_defines_get_text_token_count_signature():
    """
    Asserts that ILlmClient defines get_text_token_count with the correct signature.
    """
    import inspect

    # Act
    sig = inspect.signature(ILlmClient.get_text_token_count)

    # Assert
    assert "text" in sig.parameters
    assert "model" in sig.parameters
    assert sig.return_annotation is int


def test_llm_client_get_completion_accepts_llm_overrides():
    """The completion port carries an optional per-call persona overlay."""
    import inspect

    sig = inspect.signature(ILlmClient.get_completion)

    assert "llm_overrides" in sig.parameters
    assert sig.parameters["llm_overrides"].default is None


def test_llm_client_defines_get_token_usage_signature():
    """The usage operation takes the opaque response and returns a typed DTO."""
    import inspect

    from teddy_executor.core.domain.models.token_usage import TokenUsage

    sig = inspect.signature(ILlmClient.get_token_usage)

    assert "completion_response" in sig.parameters
    assert sig.return_annotation is TokenUsage


def test_llm_client_get_token_usage_defaults_to_zeroed_usage():
    """A client that cannot observe usage reports zeros instead of guessing."""
    from teddy_executor.core.domain.models.token_usage import TokenUsage

    class CompleteClient(ILlmClient):
        def get_completion(self, messages, model=None, llm_overrides=None, **kwargs):
            return "ok"

        def get_token_count(self, messages, model=None):
            return 0

        def get_completion_cost(self, _response, model_override=None):
            return 0.0

        def validate_config(self, _include_remote=False):
            return []

        def get_context_window(self, model=None):
            return 0

        def supports_pricing(self, model=None):
            return False

    assert CompleteClient().get_token_usage(object()) == TokenUsage()
