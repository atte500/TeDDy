"""Unit tests: every agent XML references the ``docs/templates/`` directives.

Cleanup deliverable for the templates-and-init slice. Agent prompt XMLs are
LLM-facing plaintext that is assembled verbatim (never machine-parsed). After
the blueprint extraction, each agent MUST reference ``docs/templates/`` rather
than carry inline ``<blueprints>`` sections, so artifact blueprints have a
single source of truth.
"""

from importlib import resources

AGENT_FILES = [
    "architect.xml",
    "assistant.xml",
    "debugger.xml",
    "developer.xml",
    "pathfinder.xml",
    "prototyper.xml",
]

_PROMPT_PACKAGE = "teddy_executor.resources.config.prompts"


def _read_agent_xml(filename: str) -> str:
    prompt_pkg = resources.files(_PROMPT_PACKAGE)
    return prompt_pkg.joinpath(filename).read_text(encoding="utf-8")


def test_every_agent_xml_references_docs_templates():
    """Each agent XML MUST contain an inline directive referencing ``docs/templates/``."""
    for filename in AGENT_FILES:
        content = _read_agent_xml(filename)
        assert "docs/templates/" in content, (
            f"{filename} must contain an inline directive referencing docs/templates/"
        )


def test_no_agent_xml_contains_blueprints_section():
    """No agent XML may retain an inline ``<blueprints>`` section."""
    for filename in AGENT_FILES:
        content = _read_agent_xml(filename)
        assert "<blueprints>" not in content, (
            f"{filename} must not contain an inline <blueprints> section"
        )
