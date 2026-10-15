"""Unit tests for bundled prompt file relocation."""

from importlib import resources

PROMPT_FILES = [
    "architect.md",
    "assistant.md",
    "debugger.md",
    "developer.md",
    "pathfinder.md",
    "prototyper.md",
]


def test_bundled_prompt_files_exist_at_config_prompts():
    """Verify all 6 bundled Markdown prompts live under resources/config/prompts/."""
    prompt_pkg = resources.files("teddy_executor.resources.config.prompts")
    for fname in PROMPT_FILES:
        target = prompt_pkg.joinpath(fname)
        assert target.is_file(), f"Missing bundled prompt: {target}"


def test_bundled_prompt_files_are_markdown_only():
    """After the migration the bundled prompt directory ships no `.xml` files.

    The obsolete `.xml` agent prompts are deleted, leaving only the pre-authored
    `.md` prompts under ``resources/config/prompts/``.
    """
    prompt_pkg = resources.files("teddy_executor.resources.config.prompts")
    xml_files = sorted(p.name for p in prompt_pkg.iterdir() if p.name.endswith(".xml"))
    assert xml_files == []
