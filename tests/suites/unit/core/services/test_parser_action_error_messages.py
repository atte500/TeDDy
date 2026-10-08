"""Regression tests for the plan parser's action-stream error headlines.

When the action stream meets a node that is not a valid action heading, the
surfaced (headline) message MUST name the node actually found — not only the
node expected. Otherwise the error degrades into the self-referential
``Plan content is invalid: a Level 3 Action Heading.`` which tells the plan's
author nothing about the offending content.
"""

import pytest

from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def _valid_plan_ending_in_fence() -> str:
    """A minimal, valid plan whose final node is a fenced code block.

    Ending in a fence (rather than a list item) terminates the paragraph
    context, so appended stray content becomes its own block node instead of
    being lazily folded into the preceding action's metadata list.
    """
    return (
        MarkdownPlanBuilder("Action Error Headline Regression")
        .add_create("notes.txt", "hello")
        .build()
    )


def _headline(error: InvalidPlanError) -> str:
    """Returns the first line of the error message (the surfaced headline)."""
    text = str(error)
    return text.splitlines()[0] if text else ""


def test_stray_paragraph_after_last_action_names_found_node():
    """A stray paragraph (e.g. leaked tool tags) must be named in the headline."""
    parser = MarkdownPlanParser()
    plan = _valid_plan_ending_in_fence() + "\n</parameter></invoke>\n"

    with pytest.raises(InvalidPlanError) as exc_info:
        parser.parse(plan)

    headline = _headline(exc_info.value)
    assert "but found" in headline, f"headline not informative: {headline!r}"
    assert "Paragraph" in headline, f"found node not named: {headline!r}"


def test_stray_boundary_heading_names_found_node():
    """A stray section-boundary heading must be named in the headline."""
    parser = MarkdownPlanParser()
    plan = _valid_plan_ending_in_fence() + "\n# src/parser.py::update\nvalue = 1\n"

    with pytest.raises(InvalidPlanError) as exc_info:
        parser.parse(plan)

    headline = _headline(exc_info.value)
    assert "but found" in headline, f"headline not informative: {headline!r}"
    assert "Heading (Level 1)" in headline, f"found node not named: {headline!r}"
