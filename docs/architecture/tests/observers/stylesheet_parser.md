# Component Design: StylesheetParser
- **Status:** Implemented
- **Classification:** Test Observer
- **Source:** [`tests/harness/observers/stylesheet_parser.py`](/tests/harness/observers/stylesheet_parser.py)

## Purpose
Turns a Textual stylesheet back into `{selector: {property: value}}` so a test can assert one declaration per selector. It exists because Textual layout is not observable from the harness without a screenshot, leaving the rendered CSS as the only deterministic evidence of where a panel's gutter falls.

## Consumers
- [`test_reviewer_stylesheet`](/tests/suites/unit/adapters/inbound/test_reviewer_stylesheet.py): Asserts that the shipped `ReviewerApp.CSS` carries the panel inset on both pane containers, that no child widget re-declares a padding, and that arbitrary inset pairs render through `build_tui_css`.
- [`test_stylesheet_parser`](/tests/suites/unit/test_stylesheet_parser.py): Guards this component's own parsing contract — declarations, selector lists, pseudo-classes, comments, and empty input.

## Dependencies
- **`re`** (stdlib): Provides the comment and block patterns. The module consumes no port, performs no I/O, and imports no project code, so it stays a pure function of its input.

## Class Invariants
- None — stateless module of pure functions.

## Inbound Ports
- **`parse_stylesheet(css)`**: Returns the selector-keyed declaration map for a stylesheet string.

## Outbound Ports
- None — the module requires nothing injected and reaches no external resource.

## Data Contracts
- **`{selector: {property: value}}`** (`dict[str, dict[str, str]]`): The parse result. Each comma-separated selector list expands to one entry per selector holding its own copy of the block's declarations, so mutating one selector cannot leak into its sibling. Values stay verbatim, including Textual `$variable` references and composite values such as `vkey $foreground 15%`, because the stylesheet is asserted as written rather than resolved. A selector declared by several blocks keeps the merged declarations in document order.
- **No custom exception**: malformed fragments are skipped rather than raised, so the parser never fails a test on incidental stylesheet text.

## Operations

### `parse_stylesheet(css: str) -> dict[str, dict[str, str]]`
- **Preconditions:** `css` is the stylesheet text as written; it must not be pre-stripped of comments or declarations.
- **Postconditions:** Returns one entry per distinct selector with its whitespace-trimmed declarations. Comments are removed before block matching, so a comment inside a block cannot surface as a declaration. A selector list expands into independent entries, and an empty or comment-only stylesheet returns `{}`.
- **Exceptions:** None — a fragment without a `:` separator is skipped.
