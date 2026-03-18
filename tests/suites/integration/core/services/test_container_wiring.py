from teddy_executor.container import create_container
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient


def test_container_resolves_foundational_services():
    # Arrange
    container = create_container()

    # Act
    config_service = container.resolve(IConfigService)
    llm_client = container.resolve(ILlmClient)

    # Assert
    assert isinstance(config_service, IConfigService)
    assert isinstance(llm_client, ILlmClient)
