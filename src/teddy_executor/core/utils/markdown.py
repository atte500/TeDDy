import os
import re


def get_language_from_path(path: str) -> str:
    """
    Determines the appropriate markdown code block language identifier based on a file path.
    Falls back to the extension itself, or 'text' if no extension exists.
    """
    _, ext = os.path.splitext(path)
    if not ext:
        return "text"

    ext = ext.lower().lstrip(".")

    # Common mappings where extension doesn't match language identifier exactly
    extension_map = {
        "py": "python",
        "js": "javascript",
        "jsx": "jsx",
        "ts": "typescript",
        "tsx": "tsx",
        "md": "markdown",
        "sh": "shell",
        "bash": "shell",
        "zsh": "shell",
        "yml": "yaml",
        "txt": "text",
        "ps1": "powershell",
        "cs": "csharp",
        "tf": "terraform",
        "ini": "ini",
        "cfg": "ini",
        "conf": "ini",
        "h": "c",
        "hpp": "cpp",
        "cxx": "cpp",
        "cc": "cpp",
        "rb": "ruby",
        "rs": "rust",
    }

    return extension_map.get(ext, ext)


def get_fence_for_content(content: str) -> str:
    """
    Returns a markdown code fence string (e.g., "```") that is safe to use
    for enclosing the given content.

    The length of the fence will be at least 3, and strictly greater than
    the longest sequence of backticks found in the content.
    """
    if not content:
        return "```"

    # Find all sequences of backticks
    backtick_sequences = re.findall(r"`+", content)

    max_backticks = 0
    if backtick_sequences:
        max_backticks = max(len(seq) for seq in backtick_sequences)

    # Ensure fence is at least 3, and at least one longer than max found
    fence_length = max(3, max_backticks + 1)

    return "`" * fence_length
