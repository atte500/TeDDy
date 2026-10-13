"""Shared, pure resource-path normalization helper.

Single-sources the path-normalization pipeline (Markdown-link target
extraction plus backslash -> slash conversion, exact ``./`` prefix stripping,
and leading-slash stripping) so every consumer delegates to one implementation
and the behaviour cannot drift across modules.
"""

import re

_LINK_PATTERN = re.compile(r"\[.*\]\((.*)\)")


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
