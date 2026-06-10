"""Unit tests for bundled prompt file relocation."""

from importlib import resources

PROMPT_FILES = [
    "architect.xml",
    "assistant.xml",
    "debugger.xml",
    "developer.xml",
    "pathfinder.xml",
    "prototyper.xml",
]


def test_bundled_prompt_files_exist_at_config_prompts():
    """Verify all 6 bundled prompt XMLs are located under resources/config/prompts/."""
    prompt_pkg = resources.files("teddy_executor.resources.config.prompts")
    for fname in PROMPT_FILES:
        target = prompt_pkg.joinpath(fname)
        assert target.is_file(), f"Missing bundled prompt: {target}"
