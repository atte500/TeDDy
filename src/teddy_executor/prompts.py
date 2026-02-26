from pathlib import Path
from typing import Optional


def _find_project_root(start_path: Path) -> Optional[Path]:
    """Finds the project root by searching upwards for a .git directory."""
    current_path = start_path.resolve()
    for path in [current_path] + list(current_path.parents):
        if (path / ".git").is_dir():
            return path
    return None


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
    1. A local override directory (`.teddy/prompts/`).
    2. The root-level default prompts directory (`/prompts/`).
    Returns the content as a string, or None if not found.
    """
    # 1. Search for local override
    local_prompt_dir = Path.cwd() / ".teddy" / "prompts"
    if content := _search_prompt_in_dir(local_prompt_dir, prompt_name):
        return content

    # 2. Fallback to root-level prompts
    project_root = _find_project_root(Path.cwd())
    if project_root:
        root_prompt_dir = project_root / "prompts"
        if content := _search_prompt_in_dir(root_prompt_dir, prompt_name):
            return content

    return None
