"""Sandbox replica of the proposed trailing-open-fence sanitization.

Instead of collapsing backtick runs above an arbitrary threshold, this detects
the ACTUAL defect: a code fence that is OPENED but never CLOSED -- a "trailing
opening code block". Well-formed Markdown has balanced fences; an LLM
degeneration that emits a giant run of backticks leaves an unclosed opening
fence (the observed turn-24 plan had a single ~252,310-backtick run and no
closing fence). Stripping that dangling fence removes the pathological run
without any magic number and without touching legitimate (balanced) code
blocks. All helpers are imported UNCHANGED from src/.
"""

from __future__ import annotations

import re
from typing import Dict, List

from teddy_executor.core.utils.markdown import (
    get_fence_for_content,
    get_language_from_path,
    get_session_history_display_name,
    get_session_history_sort_key,
)

# A Markdown code fence: up to 3 leading spaces, then a run of 3+ backticks or
# tildes, then an optional info string (opening) or trailing whitespace
# (closing). Runs shorter than 3 are inline code, not fences.
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def strip_trailing_open_fence(content: str) -> str:
    """Remove a trailing, UNCLOSED opening code fence from ``content``.

    Walks the fence structure: if the content ends INSIDE an open code block
    (the last fence encountered is an opening one that is never closed), that
    dangling opening fence line is removed. Balanced content -- including a
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


def format_session_history_sanitized(
    session_paths: List[str],
    file_contents: Dict[str, str | None],
) -> List[str]:
    """Sanitized variant of ContextService._format_session_history."""
    if not session_paths:
        return []

    recognized = [
        p for p in session_paths if get_session_history_display_name(p) is not None
    ]
    if not recognized:
        return []

    recognized.sort(key=get_session_history_sort_key)
    parts = ["\n## Session History"]
    for path in recognized:
        disp_name = get_session_history_display_name(path)
        content = file_contents.get(path) or ""
        content_str = strip_trailing_open_fence(content.strip())
        lang = get_language_from_path(path)
        fence = get_fence_for_content(content_str)
        parts.append(f"\n### {disp_name}")
        parts.append(f"{fence}{lang}\n{content_str}\n{fence}")
    return parts