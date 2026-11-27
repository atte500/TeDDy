"""Integration coverage for the local agent-roster adapter.

``LocalAgentCatalog`` reads the workspace's real ``.teddy/prompts/`` directory
through the production scanner, so the roster it reports is exactly the set of
personas ``teddy init prompts`` installed plus any the user added. The scanner
walks upward from the process working directory, so each case pins that
directory to an isolated temporary workspace rather than the repository.
"""

from pathlib import Path

import pytest

from teddy_executor.adapters.outbound.local_agent_catalog import LocalAgentCatalog
from teddy_executor.core.domain.models.exceptions import AgentCatalogError
from teddy_executor.core.ports.outbound import IAgentCatalog
from teddy_executor.prompts import list_prompt_names


def _workspace(tmp_path: Path, monkeypatch) -> Path:
    """Points the process working directory at an isolated workspace."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _install(workspace: Path, *filenames: str) -> None:
    """Creates ``.teddy/prompts/`` holding the named prompt files."""
    prompts = workspace / ".teddy" / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    for filename in filenames:
        (prompts / filename).write_text("prompt", encoding="utf-8")


def test_adapter_satisfies_the_agent_catalog_port():
    assert isinstance(LocalAgentCatalog(list_prompt_names), IAgentCatalog)


def test_lists_installed_personas_from_the_workspace(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path, monkeypatch)
    _install(workspace, "pathfinder.md", "developer.md")

    assert LocalAgentCatalog(list_prompt_names).list_agents() == (
        "Developer",
        "Pathfinder",
    )


def test_canonicalises_each_installed_stem(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path, monkeypatch)
    _install(workspace, "DeVeLoPeR.md")

    assert LocalAgentCatalog(list_prompt_names).list_agents() == ("Developer",)


def test_collapses_a_persona_installed_under_two_extensions(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path, monkeypatch)
    _install(workspace, "pathfinder.md", "pathfinder.xml")

    assert LocalAgentCatalog(list_prompt_names).list_agents() == ("Pathfinder",)


def test_empty_prompts_directory_reports_no_personas(tmp_path, monkeypatch):
    workspace = _workspace(tmp_path, monkeypatch)
    _install(workspace)

    assert LocalAgentCatalog(list_prompt_names).list_agents() == ()


def test_listing_failure_is_translated_into_a_catalog_error():
    def failing_lister() -> list[str]:
        raise OSError("permission denied")

    with pytest.raises(AgentCatalogError) as excinfo:
        LocalAgentCatalog(failing_lister).list_agents()

    assert "permission denied" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, OSError)
