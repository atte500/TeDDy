from pathlib import Path
from typing import Optional


def _search_prompt_in_dir(directory: Path, prompt_name: str) -> Optional[str]:
    """Searches a directory for a prompt file and returns its content."""
    if not directory.is_dir():
        return None
    found_files = list(directory.glob(f"{prompt_name}.*"))
    if found_files:
        return found_files[0].read_text(encoding="utf-8")
    return None


def find_prompt_content(prompt_name: str) -> Optional[str]:
    """
    Finds prompt content by searching in two locations:
    1. A local override directory (`.teddy/prompts/`) by searching upwards.
    2. The bundled resources directory (`src/teddy_executor/resources/prompts/`).
    Returns the content as a string, or None if not found.
    """
    # 1. Search for local override (searching upwards for .teddy)
    current_path = Path.cwd().resolve()
    for path in [current_path] + list(current_path.parents):
        local_prompt_dir = path / ".teddy" / "prompts"
        if content := _search_prompt_in_dir(local_prompt_dir, prompt_name):
            return content

    # 2. Fallback to bundled resources
    bundled_prompt_dir = Path(__file__).parent / "resources" / "prompts"
    if content := _search_prompt_in_dir(bundled_prompt_dir, prompt_name):
        return content

    return None
