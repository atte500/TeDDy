from teddy_executor.adapters.inbound.textual_plan_reviewer_logic import (
    ALLOWED_RATIONALE_SECTIONS,
    RATIONALE_FALLBACK_TITLE,
    RATIONALE_ROOT,
    _rationale_content,
    rationale_entries,
    recognized_rationale_sections,
)


def test_allowed_rationale_sections_contract():
    """Verify the white-list of rationale sections is correctly defined."""
    expected = [
        "Summary",
        "Expectation",
        "Progress",
        "Notes",
    ]
    assert ALLOWED_RATIONALE_SECTIONS == expected


def test_recognized_rationale_sections_split_on_allowed_headings():
    """Verify each allowed ### heading opens a section carrying its own body."""
    rationale = (
        "### Summary\nThe summary.\n\n"
        "### Expectation\nThe expectation.\n\n"
        "### Progress\nThe progress.\n\n"
        "### Notes\nThe notes."
    )

    assert recognized_rationale_sections(rationale) == [
        ("Summary", "The summary."),
        ("Expectation", "The expectation."),
        ("Progress", "The progress."),
        ("Notes", "The notes."),
    ]


def test_recognized_rationale_sections_merge_unrecognized_headings():
    """Verify a numeric marker and an unknown ### heading stay body text."""
    rationale = (
        "1. Synthesis\nA numeric marker is not a heading.\n\n"
        "### Summary\nThe summary.\n\n"
        "### Extra Details\nMerged into the summary."
    )

    assert recognized_rationale_sections(rationale) == [
        ("Summary", "The summary.\n\n### Extra Details\nMerged into the summary."),
    ]


def test_recognized_rationale_sections_yield_nothing_without_allowed_headings():
    """Verify a rationale written before the contract has no sections."""
    rationale = "1. Synthesis\nThe parser builds one plan per turn."

    assert recognized_rationale_sections(rationale) == []


def test_sectionless_rationale_falls_back_to_one_raw_entry():
    """Verify a rationale with no recognized heading yields one Raw entry."""
    rationale = (
        "1. Synthesis\nThe parser builds one plan per turn.\n\n"
        "2. Justification\nOne model call keeps the audit trail tight."
    )

    assert recognized_rationale_sections(rationale) == []
    assert rationale_entries(rationale) == [(RATIONALE_FALLBACK_TITLE, rationale)]


def test_structured_rationale_entries_match_its_sections():
    """Verify a structured rationale yields no raw fallback entry."""
    rationale = "### Summary\nThe summary."

    assert rationale_entries(rationale) == [("Summary", "The summary.")]


def test_blank_rationale_yields_no_entries():
    """Verify a blank rationale adds no fallback node."""
    assert rationale_entries("   ") == []


def test_rationale_content_renders_only_section_nodes():
    """Verify only a section node carries rationale Markdown to the detail pane."""
    section = {
        "type": "RATIONALE_SECTION",
        "title": "Summary",
        "content": "The summary.",
    }

    assert _rationale_content(RATIONALE_ROOT) is None
    assert _rationale_content(section) == "The summary."
