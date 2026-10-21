"""Shared, pure path helpers for resource normalization and prompt selection.

Single-sources the path-normalization pipeline (Markdown-link target
extraction plus backslash -> slash conversion, exact ``./`` prefix stripping,
leading-slash stripping, and format-character scrubbing) so every consumer
delegates to one implementation and the behaviour cannot drift across modules.
Also hosts ``prefer_markdown``, the single source of the "a pre-authored
``.md`` prompt wins over a stale ``.xml`` with the same stem" rule shared by
every prompt resolver.
"""

import re
import unicodedata
from pathlib import Path
from typing import Iterable, Optional, TypeVar

_LINK_PATTERN = re.compile(r"\[.*\]\((.*)\)")
_MARKDOWN_SUFFIX = ".md"
_T = TypeVar("_T", str, Path)

# The zero-width joiner and non-joiner are format characters, but they carry
# shaping semantics: they bind emoji sequences and control cursive joining in
# Arabic and Indic scripts, so a real file name can legitimately contain them.
_PRESERVED_FORMAT_CHARACTERS = frozenset("\u200c\u200d")


def strip_format_characters(value: str) -> str:
    """Remove format characters that occupy space but render as nothing.

    Zero-width spaces, byte-order marks, soft hyphens, and bidi controls survive
    every other normalization step. A path that carries one names a different
    file than the one it displays, so the removal happens before any other
    transformation. Shaping joiners stay because they change adjacent glyphs.
    """
    return "".join(
        char
        for char in value
        if char in _PRESERVED_FORMAT_CHARACTERS or unicodedata.category(char) != "Cf"
    )


def normalize_resource_path(resource_str: str) -> str:
    """Extracts the path from a Markdown link, or normalizes a raw path string.

    For a Markdown link ``[label](target)`` the ``target`` is extracted; any
    other input is treated as a raw path and stripped of surrounding whitespace.
    Both branches then normalize backslashes to forward slashes, strip an exact
    leading ``./`` (preserving leading dots such as ``.hidden``), and strip any
    leading ``/``. Invisible format characters are removed first, so a path
    never names a different file than the one it displays.
    """
    scrubbed = strip_format_characters(resource_str)
    match = _LINK_PATTERN.search(scrubbed)
    if match:
        normalized = match.group(1).replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized.removeprefix("./")
        return normalized.lstrip("/")

    normalized = scrubbed.strip().replace("\\", "/")
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
