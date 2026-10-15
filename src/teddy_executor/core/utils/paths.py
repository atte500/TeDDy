"""Shared, pure path helpers for resource normalization and prompt selection.

Single-sources the path-normalization pipeline (Markdown-link target
extraction plus backslash -> slash conversion, exact ``./`` prefix stripping,
and leading-slash stripping) so every consumer delegates to one implementation
and the behaviour cannot drift across modules. Also hosts ``prefer_markdown``,
the single source of the "a pre-authored ``.md`` prompt wins over a stale
``.xml`` with the same stem" rule shared by every prompt resolver.
"""

import re
from pathlib import Path
from typing import Iterable, Optional, TypeVar

_LINK_PATTERN = re.compile(r"\[.*\]\((.*)\)")
_MARKDOWN_SUFFIX = ".md"
_T = TypeVar("_T", str, Path)


def normalize_resource_path(resource_str: str) -> str:
    """Extracts the path from a Markdown link, or normalizes a raw path string.

    For a Markdown link ``[label](target)`` the ``target`` is extracted; any
    other input is treated as a raw path and stripped of surrounding whitespace.
    Both branches then normalize backslashes to forward slashes, strip an exact
    leading ``./`` (preserving leading dots such as ``.hidden``), and strip any
    leading ``/``.
    """
    match = _LINK_PATTERN.search(resource_str)
    if match:
        normalized = match.group(1).replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized.removeprefix("./")
        return normalized.lstrip("/")

    normalized = resource_str.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized.removeprefix("./")
    return normalized.lstrip("/")


def prefer_markdown(candidates: Iterable[_T]) -> Optional[_T]:
    """Returns the Markdown candidate when present, else the first candidate.

    Prompt files sharing a stem may coexist across extensions (e.g. a stale
    ``pathfinder.xml`` beside a new ``pathfinder.md``). Every prompt resolver
    routes its same-stem matches through this helper so a pre-authored Markdown
    prompt always wins regardless of directory listing order. Returns ``None``
    for an empty candidate iterable.
    """
    ordered = list(candidates)
    for candidate in ordered:
        if Path(candidate).suffix.casefold() == _MARKDOWN_SUFFIX:
            return candidate
    return ordered[0] if ordered else None
