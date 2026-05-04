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

    # Act / Assert
    # This should fail initially because validate_config is not yet
    # an abstract method in the interface (so no TypeError yet),
    # OR it will fail once I add it to the interface but not the mock.
    with pytest.raises(
        TypeError, match="Can't instantiate abstract class MockLlmClient"
    ):
        MockLlmClient()


def test_llm_client_provides_default_context_window():
    """
    Expansion Phase: The contract should provide a default implementation
    to avoid breaking existing adapters.
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

    client = MinimalClient()
    # This should fail with AttributeError until added to ILlmClient
    assert client.get_context_window() == 0
    assert client.get_context_window(model="some-model") == 0
