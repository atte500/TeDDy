"""Harness coverage for the in-memory agent-roster double.

``FakeAgentCatalog`` stands in for ``IAgentCatalog`` in reviewer tests, so a
roster must be drivable as populated, empty, or failing without reading
``.teddy/prompts/``. The port promises canonical, de-duplicated names in a
stable order, and the double honours that through the same normaliser the
adapter uses, so a test never observes a casing the reviewer would not.
"""

import pytest

from teddy_executor.core.domain.models.exceptions import AgentCatalogError
from teddy_executor.core.ports.outbound import IAgentCatalog
from tests.harness.setup.fake_agent_catalog import FakeAgentCatalog


def test_double_satisfies_the_agent_catalog_port():
    assert isinstance(FakeAgentCatalog(), IAgentCatalog)


def test_default_roster_is_populated_and_canonical():
    agents = FakeAgentCatalog().list_agents()

    assert agents
    assert all(name == name.capitalize() for name in agents)


def test_supplied_roster_is_canonicalised_deduplicated_and_ordered():
    catalog = FakeAgentCatalog(agents=("developer", "ARCHITECT", "Developer"))

    assert catalog.list_agents() == ("Developer", "Architect")


def test_empty_roster_reports_no_personas():
    catalog = FakeAgentCatalog(agents=())

    assert catalog.list_agents() == ()


def test_each_listing_is_recorded():
    catalog = FakeAgentCatalog(agents=("pathfinder",))

    catalog.list_agents()
    catalog.list_agents()

    assert catalog.list_calls == [("Pathfinder",), ("Pathfinder",)]


def test_scripted_failure_raises_agent_catalog_error():
    catalog = FakeAgentCatalog(error=AgentCatalogError("roster unreadable"))

    with pytest.raises(AgentCatalogError):
        catalog.list_agents()

    assert catalog.list_calls == [None]


def test_registration_binds_the_double_to_the_container(env):
    catalog = FakeAgentCatalog(agents=("Developer",))

    env.with_agent_catalog(catalog)

    assert env.container.resolve(IAgentCatalog) is catalog


def test_registration_defaults_to_a_fresh_double(env):
    env.with_agent_catalog()

    assert isinstance(env.container.resolve(IAgentCatalog), FakeAgentCatalog)
