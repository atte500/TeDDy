from typing import Protocol
from teddy_executor.core.domain.models import ProjectContext


class IGetContextUseCase(Protocol):
    """
    Inbound Port for the Get Context use case.
    This defines the contract for the primary entry point for gathering project context.
    """

    def get_context(self) -> ProjectContext:
        """
        Gathers all project context information.

        Returns:
            ProjectContext: A data object containing the aggregated context.
        """
        ...
