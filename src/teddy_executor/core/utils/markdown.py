import os
import re
from dataclasses import dataclass
from typing import Literal


def get_language_from_path(path: str) -> str:
    """
    Determines the appropriate markdown code block language identifier based on
    a file path. Falls back to the extension itself, or 'text' if no
    extension exists.
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


def extract_markdown_section(content: str, header: str, level: int = 2) -> str | None:
    """
    Extracts the content of a specific Markdown section.
    Returns None if the section is not found or empty.
    """
    prefix = "#" * level
    # Split by the specified header level
    sections = re.split(rf"(?m)^{prefix}\s+", content)
    for section in sections:
        if section.startswith(header):
            lines = section.splitlines()
            if len(lines) > 1:
                body = "\n".join(lines[1:]).strip()
                return body if body else None
    return None


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


# A Markdown code fence: up to 3 leading spaces, then a run of 3+ backticks or
# tildes, then an optional info string (opening) or trailing whitespace (closing).
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def strip_trailing_open_fence(content: str) -> str:
    """Remove a trailing, UNCLOSED opening code fence from ``content``.

    Walks the fence structure: if the content ends INSIDE an open code block,
    that dangling opening fence line is removed. Balanced content -- including a
    legitimate nested fence (a 4-backtick fence wrapping a 3-backtick fence) --
    is returned byte-for-byte unchanged.
    """
    lines = content.split("\n")
    open_char: str | None = None
    open_len = 0
    open_index: int | None = None

    for index, line in enumerate(lines):
        match = _FENCE_RE.match(line)
        if match is None:
            continue
        fence = match.group(1)
        info = match.group(2)
        if open_char is None:
            # Opening fence (any run >= 3 starts a block).
            open_char = fence[0]
            open_len = len(fence)
            open_index = index
        elif fence[0] == open_char and len(fence) >= open_len and not info.strip():
            # Closing fence: same char, run at least as long, no info string.
            open_char = None
            open_len = 0
            open_index = None

    if open_index is None:
        return content
    # The content ends inside an open block: strip the dangling opening fence.
    del lines[open_index]
    return "\n".join(lines)


SegmentKind = Literal["prose", "fence"]


@dataclass(frozen=True)
class MessageSegment:
    """One renderable slice of a Message body.

    ``kind`` is ``"prose"`` or ``"fence"``. A fence segment carries its own raw
    ``opening`` and ``closing`` delimiter lines, so tilde fences, indented
    fences, and longer closing runs survive re-emission byte-for-byte.
    ``closing`` is empty when the body ends inside an open fence.
    """

    kind: SegmentKind
    info: str = ""
    content: str = ""
    opening: str = ""
    closing: str = ""


def _closing_fence_index(lines: list[str], start: int, opening_run: str) -> int | None:
    """Return the index of the line closing ``opening_run``, or None if unclosed.

    A closing fence repeats the opening character, runs at least as long, and
    carries no info string, so a line starting with a backtick run inside a
    tilde block stays content.
    """
    for index in range(start, len(lines)):
        candidate = _FENCE_RE.match(lines[index])
        if candidate is None:
            continue
        run = candidate.group(1)
        if run[0] != opening_run[0] or len(run) < len(opening_run):
            continue
        if candidate.group(2).strip():
            continue
        return index
    return None


def _flush_prose(segments: list[MessageSegment], prose: list[str]) -> None:
    """Append the accumulated prose run, dropping whitespace-only runs."""
    if any(line.strip() for line in prose):
        segments.append(MessageSegment(kind="prose", content="\n".join(prose)))
    prose.clear()


def split_fenced_segments(body: str) -> list[MessageSegment]:
    """Split a Markdown body into prose runs and fenced blocks.

    Fences are read with the same grammar `strip_trailing_open_fence` uses: up
    to three leading spaces, a run of three or more backticks or tildes, and an
    optional info string. A closing fence must repeat the opening character, run
    at least as long, and carry no info string, so a line starting with a
    backtick run inside a tilde block stays content.

    Whitespace-only prose runs are dropped: the renderer owns the spacing around
    a fence, so a blank line between two blocks carries no information.
    """
    lines = body.split("\n")
    segments: list[MessageSegment] = []
    prose: list[str] = []
    index = 0

    while index < len(lines):
        match = _FENCE_RE.match(lines[index])
        if match is None:
            prose.append(lines[index])
            index += 1
            continue
        _flush_prose(segments, prose)
        closing_index = _closing_fence_index(lines, index + 1, match.group(1))
        end = closing_index if closing_index is not None else len(lines)
        segments.append(
            MessageSegment(
                kind="fence",
                info=match.group(2).strip(),
                content="\n".join(lines[index + 1 : end]),
                opening=lines[index],
                closing=lines[end] if closing_index is not None else "",
            )
        )
        index = end + 1

    _flush_prose(segments, prose)
    return segments


def embed_in_fence(content: str, lang: str) -> str:
    """Sanitize ``content``, then wrap it in a safe, dynamically-sized fence.

    Strips a trailing UNCLOSED fence BEFORE deriving the wrapper fence, so a
    degenerate run cannot amplify the wrapper. The wrapper fence is sized from
    the sanitized content, so it can never collide with content fences.
    """
    sanitized = strip_trailing_open_fence(content)
    fence = get_fence_for_content(sanitized)
    return f"{fence}{lang}\n{sanitized}\n{fence}"


def _normalize_session_path(path: str) -> str:
    """Normalize a path to POSIX slashes with any leading './' removed."""
    return path.replace("\\", "/").lstrip("./")


def _session_directory_name(session_root: str) -> str:
    """Return the final path component of a session root (its directory name)."""
    return _normalize_session_path(session_root).rstrip("/").rsplit("/", 1)[-1]


def is_own_session_path(path: str, session_root: str | None) -> bool:
    """
    Determines whether ``path`` belongs to the session at ``session_root``.

    Falls back to the coarse ``is_session_file_path`` test when no root is
    supplied, so legacy callers keep their session-agnostic partition.
    """
    if not is_session_file_path(path):
        return False
    if not session_root:
        return True
    session_name = _session_directory_name(session_root)
    return session_name in _normalize_session_path(path).split("/")


def get_session_history_display_name(
    path: str, session_root: str | None = None
) -> str | None:
    """
    Returns human-readable display name if it's a recognized session history file.

    When ``session_root`` is supplied, a path outside that session is not history.
    """
    if session_root and not is_own_session_path(path, session_root):
        return None
    clean_path = _normalize_session_path(path)
    if "initial_request.md" in clean_path:
        return "Initial Request"
    plan_match = re.search(r"sessions/[^/]+/(\d+)/plan.md$", clean_path)
    if plan_match:
        return f"Turn {int(plan_match.group(1))}: Plan"
    report_match = re.search(r"sessions/[^/]+/(\d+)/report.md$", clean_path)
    if report_match:
        return f"Turn {int(report_match.group(1))}: Report"
    return None


def is_session_file_path(path: str) -> bool:
    """
    Determines if a path is inside .teddy/sessions/.

    Normalizes backslashes first, so a Windows-style path is recognized too.
    """
    return "sessions/" in _normalize_session_path(path)


def is_session_history_path(path: str, session_root: str | None = None) -> bool:
    """
    Determines if a path is a session history file for ``session_root``.
    """
    return get_session_history_display_name(path, session_root) is not None


def get_session_history_sort_key(path: str) -> tuple[int, int]:
    """
    Sort key for chronological session history: (turn_number, sub_order).
    """
    clean_path = _normalize_session_path(path)
    if "initial_request.md" in clean_path:
        return (0, 0)
    plan_match = re.search(r"sessions/[^/]+/(\d+)/plan.md$", clean_path)
    if plan_match:
        return (int(plan_match.group(1)), 1)
    report_match = re.search(r"sessions/[^/]+/(\d+)/report.md$", clean_path)
    if report_match:
        return (int(report_match.group(1)), 2)
    return (999999, 999999)
