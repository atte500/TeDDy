from typing import Protocol, runtime_checkable


@runtime_checkable
class IAgentCatalog(Protocol):
    """
    An outbound port for discovering which agent personas the workspace declares.

    The roster is discovered rather than fixed, because a workspace may carry a
    reduced, extended, or empty set of prompt files.
    """

    def list_agents(self) -> tuple[str, ...]:
        """
        Lists the workspace's installed agent personas.

        Postconditions:
            Returns canonical, de-duplicated names in a stable order, so the
            selection menu renders identically across calls. An empty tuple
            means no persona is installed.

        Raises:
            AgentCatalogError: When the roster cannot be read.
        """
        ...
