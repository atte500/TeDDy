"""Concrete IAgentCatalog backed by the workspace's ``.teddy/prompts/`` scan."""

from collections.abc import Callable

from teddy_executor.core.domain.models.exceptions import AgentCatalogError
from teddy_executor.core.ports.outbound.agent_catalog import IAgentCatalog
from teddy_executor.core.utils.string import canonical_agent_name


class LocalAgentCatalog(IAgentCatalog):
    """Lists the personas the workspace installs, through the prompt scanner.

    The scanner is injected rather than imported, so the adapter carries no
    concrete discovery mechanism: production supplies ``list_prompt_names``,
    which walks upward from the working directory, and a test supplies the same
    scanner bound to an isolated workspace.
    """

    def __init__(self, list_prompt_names: Callable[[], list[str]]) -> None:
        self._list_prompt_names = list_prompt_names

    def list_agents(self) -> tuple[str, ...]:
        """Lists the installed personas as canonical, de-duplicated names.

        The scanner's order is preserved, because canonicalisation only re-cases
        each name, so the roster renders identically across calls. A persona
        installed under two extensions collapses onto its first appearance.
        """
        try:
            names = self._list_prompt_names()
        except OSError as error:
            raise AgentCatalogError(
                f"Failed to list agent personas: {error}"
            ) from error
        return tuple(dict.fromkeys(canonical_agent_name(name) for name in names))
