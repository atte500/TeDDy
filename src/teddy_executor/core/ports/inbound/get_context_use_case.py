from typing import Dict, Optional, Protocol, Sequence
from teddy_executor.core.domain.models import ProjectContext


class IGetContextUseCase(Protocol):
    """
    Inbound Port for the Get Context use case.
    This defines the contract for the primary entry point for gathering project context.
    """

    def get_context(
        self, context_files: Optional[Dict[str, Sequence[str]]] = None
    ) -> ProjectContext:
        """
        Gathers all project context information.

        Args:
            context_files: Optional mapping of scope names to .context files.

        Returns:
            ProjectContext: A data object containing the aggregated context.
        """
        ...
