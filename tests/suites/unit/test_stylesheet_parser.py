"""Unit tests for the stylesheet parser harness observer.

The reviewer's panel insets live in one CSS string, and Textual layout is not
observable from the harness, so a gutter can only be pinned by parsing the
rendered stylesheet. ``parse_stylesheet`` turns that string into
``{selector: {property: value}}``, letting a test assert a single declaration
per selector instead of matching the whole document.
"""

from tests.harness.observers.stylesheet_parser import parse_stylesheet


class TestDeclarations:
    def test_parses_a_block_into_a_property_map(self):
        css = parse_stylesheet("#left-pane {\n    width: 65%;\n    padding: 0 1;\n}")

        assert css["#left-pane"] == {"width": "65%", "padding": "0 1"}

    def test_keeps_textual_variables_verbatim(self):
        css = parse_stylesheet(
            "#right-pane { border-left: vkey $foreground 15%; background: $surface; }"
        )

        assert css["#right-pane"]["border-left"] == "vkey $foreground 15%"
        assert css["#right-pane"]["background"] == "$surface"

    def test_strips_surrounding_whitespace_from_values(self):
        css = parse_stylesheet("Tree {   height:  1fr  ; }")

        assert css["Tree"] == {"height": "1fr"}


class TestSelectors:
    def test_keeps_each_selector_separate(self):
        css = parse_stylesheet("Tree { height: 1fr; }\nListItem { height: auto; }")

        assert css["Tree"] == {"height": "1fr"}
        assert css["ListItem"] == {"height": "auto"}

    def test_expands_comma_separated_selectors(self):
        css = parse_stylesheet("#first-pane, #second-pane { padding: 0 1; }")

        assert css["#first-pane"] == {"padding": "0 1"}
        assert css["#second-pane"] == {"padding": "0 1"}

    def test_keeps_a_pseudo_class_selector_intact(self):
        css = parse_stylesheet(
            "#right-pane:focus-within { background: $surface-lighten-1; }"
        )

        assert css["#right-pane:focus-within"] == {"background": "$surface-lighten-1"}


class TestIgnoredContent:
    def test_returns_an_empty_mapping_for_an_empty_stylesheet(self):
        assert parse_stylesheet("") == {}

    def test_skips_a_comment_only_stylesheet(self):
        assert parse_stylesheet("/* The reviewer stylesheet. */") == {}

    def test_ignores_a_comment_inside_a_block(self):
        css = parse_stylesheet("Tree { /* fills the pane height */ height: 1fr; }")

        assert css["Tree"] == {"height": "1fr"}
