"""Contract tests for the canonical rationale scenarios.

The reviewer renders one tree node per level-three heading, so these tests pin
what each scenario promises: a section renders its heading line and body, a
fence keeps a `### ` line inside its block, and a variant named for a branch
really carries the line that branch turns on.
"""

import pytest

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
    fenced,
    rationale,
    section,
    sections,
)


def headings_in(text: str) -> list[str]:
    """Every level-three heading line ``text`` carries, in order."""
    return [line for line in text.splitlines() if line.startswith("### ")]


def test_section_renders_a_heading_line_then_the_body():
    lines = section("Summary", "The summary.").splitlines()

    assert lines == ["### Summary", "The summary."]


def test_rationale_joins_blocks_with_one_blank_line():
    assert rationale("first", "second") == "first\n\nsecond"


def test_sections_renders_every_pair_in_order():
    rendered = sections([("Summary", "The summary."), ("Notes", "The notes.")])

    assert rendered == "### Summary\nThe summary.\n\n### Notes\nThe notes."


@pytest.mark.parametrize("fence", ["```", "~~~", "````"])
def test_fenced_opens_and_closes_with_the_same_fence(fence):
    lines = fenced("body", fence=fence).splitlines()

    assert lines == [fence, "body", fence]


def test_protocol_sections_are_the_four_authored_titles():
    assert [title for title, _ in PROTOCOL_SECTIONS] == [
        "Summary",
        "Expectation",
        "Progress",
        "Notes",
    ]


def test_non_protocol_titles_are_disjoint_from_the_authored_ones():
    authored = {title for title, _ in PROTOCOL_SECTIONS}

    assert {title for title, _ in NON_PROTOCOL_SECTIONS}.isdisjoint(authored)


def test_protocol_rationale_carries_one_heading_per_authored_section():
    assert headings_in(PROTOCOL_RATIONALE) == [
        f"### {title}" for title, _ in PROTOCOL_SECTIONS
    ]


def test_non_protocol_rationale_carries_only_its_own_headings():
    assert headings_in(NON_PROTOCOL_RATIONALE) == [
        f"### {title}" for title, _ in NON_PROTOCOL_SECTIONS
    ]


def test_mixed_rationale_orders_preamble_then_protocol_then_non_protocol():
    assert MIXED_RATIONALE.startswith(f"{PREAMBLE}\n\n")
    assert MIXED_RATIONALE.index("### Notes") < MIXED_RATIONALE.index("### Context")


def test_preamble_rationale_keeps_text_before_its_first_heading():
    assert PREAMBLE_RATIONALE.startswith(f"{PREAMBLE}\n\n")
    assert headings_in(PREAMBLE_RATIONALE) == ["### Summary"]


def test_headingless_rationale_carries_no_level_three_heading():
    assert headings_in(HEADINGLESS_RATIONALE) == []


@pytest.mark.parametrize("variant", sorted(FENCED_HEADING_RATIONALES))
def test_every_fenced_variant_hides_a_level_three_heading(variant):
    assert HIDDEN_HEADING in FENCED_HEADING_RATIONALES[variant].splitlines()


@pytest.mark.parametrize("variant", sorted(NON_SPLITTING_LINES))
def test_non_splitting_variants_never_open_a_level_three_heading(variant):
    assert headings_in(NON_SPLITTING_LINES[variant]) == []


def test_non_splitting_variants_carry_their_distinguishing_prefix():
    assert NON_SPLITTING_LINES["four_hashes"].startswith("#### ")
    assert NON_SPLITTING_LINES["indented"].startswith("   ### ")
    assert NON_SPLITTING_LINES["numeric_marker"].startswith("1. ")


def test_empty_section_variant_places_two_headings_back_to_back():
    assert EMPTY_SECTION_RATIONALE.splitlines()[:2] == ["### Progress", "### Notes"]


def test_duplicate_title_variant_repeats_the_same_heading():
    assert headings_in(DUPLICATE_TITLE_RATIONALE) == ["### Notes", "### Notes"]


def test_trailing_whitespace_variant_keeps_spaces_on_the_heading():
    assert TRAILING_WHITESPACE_HEADING.splitlines()[0] == "### Notes   "
