from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient


def test_container_resolves_foundational_services(container):
    """
    Integration test ensuring the DI container correctly resolves foundational
    outbound ports.
    """
    # Act
    config_service = container.resolve(IConfigService)
    llm_client = container.resolve(ILlmClient)

    # Assert
    assert config_service is not None
    assert llm_client is not None
    # We assert on the interface/port type since the implementation might be
    # a mock depending on the fixture's configuration.
    assert isinstance(config_service, IConfigService)
    assert isinstance(llm_client, ILlmClient)
