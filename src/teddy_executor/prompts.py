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
    Finds prompt content by searching in `.teddy/prompts/` (user-editable)
    by traversing upwards from the current working directory.
    Returns the content as a string, or None if not found.
    Bundled resources are no longer used as a fallback — only `.teddy/prompts/`.
    """
    current_path = Path.cwd().resolve()
    for path in [current_path] + list(current_path.parents):
        local_prompt_dir = path / ".teddy" / "prompts"
        if content := _search_prompt_in_dir(local_prompt_dir, prompt_name):
            return content

    return None


def list_prompt_names() -> list[str]:
    """
    Lists available prompt names by scanning `.teddy/prompts/` directories
    upward from the current working directory.
    Returns a sorted list of prompt names (stems, without any file extension),
    or an empty list if no prompts directory is found.
    """
    current_path = Path.cwd().resolve()
    for path in [current_path] + list(current_path.parents):
        prompts_dir = path / ".teddy" / "prompts"
        if prompts_dir.is_dir():
            # List all files in the prompts directory and extract stems
            prompt_files = sorted(prompts_dir.glob("*"))
            return [f.stem for f in prompt_files if f.is_file()]
    return []
