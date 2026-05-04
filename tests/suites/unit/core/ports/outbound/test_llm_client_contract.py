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
