from typing import Optional, Protocol, Sequence
from teddy_executor.core.domain.models import ProjectContext


class IGetContextUseCase(Protocol):
    """
    Inbound Port for the Get Context use case.
    This defines the contract for the primary entry point for gathering project context.
    """

    def get_context(
        self, context_files: Optional[Sequence[str]] = None
    ) -> ProjectContext:
        """
        Gathers all project context information.

        Args:
            context_files: Optional list of .context files to resolve paths from.

        Returns:
            ProjectContext: A data object containing the aggregated context.
        """
        ...
