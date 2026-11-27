"""In-memory fake for the IAgentCatalog outbound port."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from teddy_executor.core.domain.models.exceptions import AgentCatalogError
from teddy_executor.core.services.init_service import _PROMPT_FILES
from teddy_executor.core.utils.string import canonical_agent_name

DEFAULT_AGENTS: tuple[str, ...] = tuple(
    canonical_agent_name(Path(filename).stem) for filename in _PROMPT_FILES
)


class FakeAgentCatalog:
    """Deterministic ``IAgentCatalog`` double for harness-driven reviewer tests.

    Holds a roster that can be populated, empty, or scripted to fail, and
    applies the port's postconditions the way the real adapter must: names are
    canonicalised through the shared ``canonical_agent_name``, duplicates
    collapse on their first appearance, and the surviving order is the order
    the roster was declared in. A scripted ``AgentCatalogError`` fails the
    listing before any roster is computed, matching the port's promise that an
    unreadable roster reports rather than renders as empty.

    The default roster derives from the bundled prompt manifest, so it cannot
    drift from the personas ``teddy init prompts`` installs. ``list_calls``
    records the roster each listing answered, or ``None`` for a scripted
    failure, so a test can tell never-listed from listed-and-answered from
    listed-and-failed.
    """

    def __init__(
        self,
        agents: Optional[Sequence[str]] = None,
        error: Optional[AgentCatalogError] = None,
    ) -> None:
        self._agents: tuple[str, ...] = (
            tuple(agents) if agents is not None else DEFAULT_AGENTS
        )
        self._error = error
        self.list_calls: list[Optional[tuple[str, ...]]] = []

    def list_agents(self) -> tuple[str, ...]:
        if self._error is not None:
            self.list_calls.append(None)
            raise self._error
        roster = tuple(dict.fromkeys(canonical_agent_name(a) for a in self._agents))
        self.list_calls.append(roster)
        return roster
