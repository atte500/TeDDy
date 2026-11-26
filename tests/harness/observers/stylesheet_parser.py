"""Parse a Textual stylesheet into a selector-keyed declaration map.

The reviewer's gutters live in one CSS string, and Textual layout is not
observable from the harness without a screenshot, so a padding can only be
pinned by reading the rendered stylesheet. ``parse_stylesheet`` turns that
string into ``{selector: {property: value}}``, so a test asserts one
declaration per selector and a stray second declaration shows up as a readable
diff instead of an opaque whole-document comparison.
"""

import re

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}")


def parse_stylesheet(css: str) -> dict[str, dict[str, str]]:
    """Return every selector's declarations, stripped of comments and whitespace.

    A comma-separated selector list expands to one entry per selector, each
    holding its own copy of the block's declarations, so mutating one selector
    cannot leak into its sibling. Textual's ``$variable`` references and
    composite values such as ``vkey $foreground 15%`` are kept verbatim,
    because the stylesheet is asserted as written rather than resolved. A
    selector declared by several blocks keeps the merged declarations in
    document order.
    """
    declarations_by_selector: dict[str, dict[str, str]] = {}

    for block in _BLOCK.finditer(_COMMENT.sub("", css)):
        selectors, body = block.group(1), block.group(2)
        declarations = _parse_declarations(body)
        for selector in selectors.split(","):
            name = selector.strip()
            if name:
                declarations_by_selector.setdefault(name, {}).update(declarations)

    return declarations_by_selector


def _parse_declarations(body: str) -> dict[str, str]:
    """Split a block body on ``;``, keeping only well-formed declarations."""
    declarations: dict[str, str] = {}

    for declaration in body.split(";"):
        property_name, separator, value = declaration.partition(":")
        if not separator:
            continue
        declarations[property_name.strip()] = value.strip()

    return declarations
