"""Canonical rationale scenarios for reviewer splitter tests.

The reviewer renders one tree node per level-three heading, so the branches
that matter are the ones a heading or a fence can hide: preamble text, a
heading behind a fence, a deeper heading, an indented heading, an empty
section, and duplicate titles. These scenarios build those rationales from
named fragments, so a splitter test drives a real branch instead of
hand-writing Markdown that drifts from the fixture.

The module is data only: it imports no reviewer code, so a test cannot couple
to the implementation it exercises.
"""

from collections.abc import Iterable

PREAMBLE = "Written before any heading."

PROTOCOL_SECTIONS: tuple[tuple[str, str], ...] = (
    ("Summary", "The summary."),
    ("Expectation", "The expectation."),
    ("Progress", "The progress."),
    ("Notes", "The notes."),
)

NON_PROTOCOL_SECTIONS: tuple[tuple[str, str], ...] = (
    ("Context", "The context."),
    ("Trade-offs", "The trade-offs."),
)

HIDDEN_HEADING = "### Hidden behind a fence"


def section(title: str, body: str) -> str:
    """One level-three section: its heading line, then its body verbatim."""
    return f"### {title}\n{body}"


def fenced(body: str, fence: str = "```") -> str:
    """A fenced block whose closer matches its opener."""
    return f"{fence}\n{body}\n{fence}"


def rationale(*blocks: str) -> str:
    """Join blocks with one blank line, the way a plan carries them.

    Blocks carry no trailing newline, so the join leaves exactly one blank
    line between two of them.
    """
    return "\n\n".join(blocks)


def sections(pairs: Iterable[tuple[str, str]]) -> str:
    """Render consecutive sections from ``(title, body)`` pairs."""
    return rationale(*(section(title, body) for title, body in pairs))


PROTOCOL_RATIONALE = sections(PROTOCOL_SECTIONS)
NON_PROTOCOL_RATIONALE = sections(NON_PROTOCOL_SECTIONS)
MIXED_RATIONALE = rationale(PREAMBLE, PROTOCOL_RATIONALE, NON_PROTOCOL_RATIONALE)
PREAMBLE_RATIONALE = rationale(PREAMBLE, section("Summary", "The summary."))
HEADINGLESS_RATIONALE = rationale(
    "1. Synthesis\nThe parser builds one plan per turn.",
    "2. Justification\nOne model call keeps the audit trail tight.",
)

FENCED_HEADING_RATIONALES: dict[str, str] = {
    "backtick": rationale(
        section("Notes", fenced(f"{HIDDEN_HEADING}\nBacktick body."))
    ),
    "tilde": rationale(
        section("Notes", fenced(f"{HIDDEN_HEADING}\nTilde body.", fence="~~~"))
    ),
    "longer": rationale(
        section("Notes", fenced(f"```\n{HIDDEN_HEADING}\n```", fence="````"))
    ),
    "unclosed": f"### Notes\nThe notes.\n\n```\n{HIDDEN_HEADING}\nBody.",
}

NON_SPLITTING_LINES: dict[str, str] = {
    "four_hashes": "#### Deeper heading\nNot a section boundary.",
    "indented": "   ### Indented heading\nNot a section boundary.",
    "numeric_marker": "1. Numeric marker\nNot a section boundary.",
}

EMPTY_SECTION_RATIONALE = "### Progress\n### Notes\nThe notes."
DUPLICATE_TITLE_RATIONALE = "### Notes\nFirst.\n\n### Notes\nSecond."
TRAILING_WHITESPACE_HEADING = "### Notes   \nThe notes."
