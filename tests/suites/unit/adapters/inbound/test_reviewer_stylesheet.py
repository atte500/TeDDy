"""Stylesheet contract for the reviewer's shared panel inset.

Textual layout is not observable from the harness without a screenshot, so the
one-gutter rule is pinned against the rendered stylesheet: both pane containers
carry the same inset and no child widget re-declares one, because CSS padding
stacks and a second declaration reintroduces the drift.
"""

import pytest

from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.adapters.inbound.textual_plan_reviewer_widgets import (
    PANEL_INSET,
    build_tui_css,
)
from tests.harness.observers.stylesheet_parser import parse_stylesheet

PANES = ("#left-pane", "#right-pane")
CHILDREN_WITHOUT_INSET = ("#rationale-content", "ListItem", "Tree")


def css_padding(inset: tuple[int, int]) -> str:
    """The CSS ``padding`` value an inset pair renders to."""
    return f"{inset[0]} {inset[1]}"


class TestShippedStylesheet:
    """The stylesheet the reviewer app actually binds."""

    def test_both_panes_carry_the_panel_inset(self):
        stylesheet = parse_stylesheet(ReviewerApp.CSS)

        for pane in PANES:
            assert stylesheet[pane]["padding"] == css_padding(PANEL_INSET), pane

    def test_no_child_widget_declares_a_second_inset(self):
        stylesheet = parse_stylesheet(ReviewerApp.CSS)

        for selector in CHILDREN_WITHOUT_INSET:
            assert "padding" not in stylesheet[selector], selector

    def test_right_pane_keeps_the_left_border_the_inset_sits_inside(self):
        stylesheet = parse_stylesheet(ReviewerApp.CSS)

        assert "border-left" in stylesheet["#right-pane"]


class TestSubstitution:
    @pytest.mark.parametrize("inset", [(0, 0), (0, 3), (1, 2), (2, 1)])
    def test_renders_the_given_pair_into_both_panes(self, inset):
        stylesheet = parse_stylesheet(build_tui_css(inset))

        for pane in PANES:
            assert stylesheet[pane]["padding"] == css_padding(inset), pane
