"""Contract tests for the fence-aware rationale splitter.

The reviewer renders one tree node per section its author wrote, so the
splitter decides what a reviewer sees: every level-three heading opens a
section whatever its title, a fence hides the headings inside it, and
untitled content stays visible under a fallback label. Every case drives one
branch from ``tests.harness.setup.rationale_scenarios``.
"""

import pytest

from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    RATIONALE_FALLBACK_TITLE,
    RATIONALE_ROOT,
    _rationale_content,
    rationale_sections,
)
from tests.harness.setup.rationale_scenarios import (
    DUPLICATE_TITLE_RATIONALE,
    EMPTY_SECTION_RATIONALE,
    FENCED_HEADING_RATIONALES,
    HEADINGLESS_RATIONALE,
    HIDDEN_HEADING,
    MIXED_RATIONALE,
    NON_PROTOCOL_RATIONALE,
    NON_PROTOCOL_SECTIONS,
    NON_SPLITTING_LINES,
    PREAMBLE,
    PREAMBLE_RATIONALE,
    PROTOCOL_RATIONALE,
    PROTOCOL_SECTIONS,
    TRAILING_WHITESPACE_HEADING,
)


def test_fallback_title_labels_untitled_content():
    assert RATIONALE_FALLBACK_TITLE == "Untitled"


def test_protocol_rationale_yields_one_section_per_authored_heading():
    assert rationale_sections(PROTOCOL_RATIONALE) == list(PROTOCOL_SECTIONS)


def test_non_protocol_headings_each_open_their_own_section():
    assert rationale_sections(NON_PROTOCOL_RATIONALE) == list(NON_PROTOCOL_SECTIONS)


def test_preamble_renders_as_a_leading_untitled_section():
    assert rationale_sections(PREAMBLE_RATIONALE) == [
        (RATIONALE_FALLBACK_TITLE, PREAMBLE),
        ("Summary", "The summary."),
    ]


def test_headingless_rationale_renders_as_one_untitled_section():
    assert rationale_sections(HEADINGLESS_RATIONALE) == [
        (RATIONALE_FALLBACK_TITLE, HEADINGLESS_RATIONALE)
    ]


@pytest.mark.parametrize("rationale", ["", "   ", "\n\n"])
def test_blank_rationale_yields_no_sections(rationale):
    assert rationale_sections(rationale) == []


def test_mixed_rationale_keeps_every_section_in_authored_order():
    sections = rationale_sections(MIXED_RATIONALE)

    assert [title for title, _ in sections] == [
        RATIONALE_FALLBACK_TITLE,
        *(title for title, _ in PROTOCOL_SECTIONS),
        *(title for title, _ in NON_PROTOCOL_SECTIONS),
    ]
    assert sections[0][1] == PREAMBLE


@pytest.mark.parametrize("variant", sorted(FENCED_HEADING_RATIONALES))
def test_a_fence_keeps_its_heading_inside_the_enclosing_section(variant):
    sections = rationale_sections(FENCED_HEADING_RATIONALES[variant])

    assert [title for title, _ in sections] == ["Notes"]
    assert HIDDEN_HEADING in sections[0][1]


@pytest.mark.parametrize("variant", sorted(NON_SPLITTING_LINES))
def test_a_non_heading_line_stays_untitled_body(variant):
    rationale = NON_SPLITTING_LINES[variant]

    assert rationale_sections(rationale) == [(RATIONALE_FALLBACK_TITLE, rationale)]


def test_empty_section_survives_with_an_empty_body():
    assert rationale_sections(EMPTY_SECTION_RATIONALE) == [
        ("Progress", ""),
        ("Notes", "The notes."),
    ]


def test_duplicate_titles_yield_both_sections_in_order():
    assert rationale_sections(DUPLICATE_TITLE_RATIONALE) == [
        ("Notes", "First."),
        ("Notes", "Second."),
    ]


def test_trailing_whitespace_is_stripped_from_the_title():
    assert rationale_sections(TRAILING_WHITESPACE_HEADING) == [("Notes", "The notes.")]


def test_rationale_content_renders_only_section_nodes():
    """Only a section node carries rationale Markdown to the detail pane."""
    section_node = {
        "type": "RATIONALE_SECTION",
        "title": "Summary",
        "content": "The summary.",
    }

    assert _rationale_content(RATIONALE_ROOT) is None
    assert _rationale_content(section_node) == "The summary."
