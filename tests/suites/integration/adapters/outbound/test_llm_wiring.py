from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.adapters.outbound.openrouter_hydrator import (
    OpenRouterMetadataHydrator,
)


def test_litellm_adapter_is_wired_with_hydrator(container):
    """
    Ensures that the ILlmClient resolved from the container has
    an OpenRouterMetadataHydrator injected.
    """
    # Act
    llm_client = container.resolve(ILlmClient)

    # Assert
    assert isinstance(llm_client, LiteLLMAdapter)
    # Accessing private attribute for wiring verification
    assert isinstance(llm_client._hydrator, OpenRouterMetadataHydrator)
