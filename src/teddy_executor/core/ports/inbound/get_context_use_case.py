from typing import Dict, Optional, Protocol, Sequence
from teddy_executor.core.domain.models import ProjectContext


class IGetContextUseCase(Protocol):
    """
    Inbound Port for the Get Context use case.
    This defines the contract for the primary entry point for gathering project context.
    """

    def get_context(  # noqa: PLR0913 - inbound-port seam; additive keywords
        self,
        context_files: Optional[Dict[str, Sequence[str]]] = None,
        include_tokens: bool = True,
        agent_name: str = "Unknown",
        total_window: int = 0,
        current_turn: Optional[str] = None,
        system_prompt_tokens: int = 0,
        session_root: Optional[str] = None,
        model: Optional[str] = None,
        session_cost: Optional[float] = None,
    ) -> ProjectContext:
        """
        Gathers all project context information.

        Args:
            context_files: Optional mapping of scope names to .context files.
            current_turn: Optional 2-digit turn number to include in the header.
            system_prompt_tokens: Token count of the system prompt (pre-computed).
            session_root: Optional root of the rendering session, used to gate
                session-history classification.
            model: Optional effective model used for token counting. Omitted,
                the provider's configured model is used. Also names the model
                the reviewer displays, with a blank value resolving to
                ``Unknown``.
            session_cost: Optional accumulated session cost. ``None`` means no
                figure was recorded; ``0.0`` is a recorded zero.

        Returns:
            ProjectContext: A data object containing the aggregated context.
        """
        ...
