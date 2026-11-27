from typing import Protocol, runtime_checkable

from teddy_executor.core.domain.models.exceptions import AgentCatalogError, TeddyError
from teddy_executor.core.ports.outbound import IAgentCatalog


class _ConformingCatalog:
    """A hand-written double declaring exactly the port's single member."""

    def list_agents(self) -> tuple[str, ...]:
        return ("Developer", "Pathfinder")


class _MissingListAgents:
    """A double that drifted from the contract by omitting the member."""

    def list_personas(self) -> tuple[str, ...]:
        return ()


def test_agent_catalog_port_is_runtime_checkable():
    assert issubclass(IAgentCatalog, Protocol), "IAgentCatalog must be a Protocol"
    assert runtime_checkable(IAgentCatalog), (
        "IAgentCatalog must be runtime_checkable so a drifted double is rejected "
        "at the boundary instead of failing deep inside the reviewer"
    )


def test_agent_catalog_port_declares_list_agents():
    assert callable(getattr(IAgentCatalog, "list_agents", None)), (
        "IAgentCatalog must declare list_agents"
    )


def test_object_with_list_agents_satisfies_the_port():
    assert isinstance(_ConformingCatalog(), IAgentCatalog)


def test_object_without_list_agents_does_not_satisfy_the_port():
    assert not isinstance(_MissingListAgents(), IAgentCatalog)


def test_agent_catalog_error_is_a_teddy_error():
    assert issubclass(AgentCatalogError, TeddyError), (
        "AgentCatalogError must inherit TeddyError so the boundary reports a "
        "roster failure as a user-facing error instead of a raw traceback"
    )
