# Component Design: RationaleScenarios
- **Status:** Implemented
- **Classification:** Test Setup
- **Source:** [`tests/harness/setup/rationale_scenarios.py`](/tests/harness/setup/rationale_scenarios.py)

## Purpose
Supplies the canonical rationales the reviewer's fence-aware splitter tests drive, built from named fragments so a test states which branch it exercises instead of hand-writing Markdown that drifts from the fixture.

## Consumers
- [`test_rationale_sections.py`](/tests/suites/unit/adapters/inbound/test_rationale_sections.py): Drives every splitter branch, namely preamble, non-protocol titles, the four fence variants, non-splitting lines, an empty section, duplicate titles, and a trailing-space heading.
- [`test_tui_rationale_parsing.py`](/tests/suites/acceptance/test_tui_rationale_parsing.py): Composes a preamble-plus-authored-headings rationale, so the reviewer tree is exercised through the real adapter boundary.
- [`test_rationale_scenarios_harness.py`](/tests/suites/unit/test_rationale_scenarios_harness.py): Pins the shape each scenario promises, so a variant cannot quietly stop carrying the line its branch turns on.

## Dependencies
- None. The module is data only: it imports nothing from `teddy_executor`, so a test using it cannot couple to the implementation it exercises.

## Class Invariants
- `data_only`: The module defines constants and pure string builders and imports no reviewer, splitter, or domain code, so importing it cannot drag reviewer state into a unit test.
- `fragments_compose_every_fixture`: `section`, `fenced`, `rationale`, and `sections` produce the named fixtures, so a scenario names the branch it drives instead of carrying opaque Markdown.
- `literal_shapes_where_a_helper_would_hide_them`: `EMPTY_SECTION_RATIONALE`, `DUPLICATE_TITLE_RATIONALE`, `TRAILING_WHITESPACE_HEADING`, `NON_SPLITTING_LINES`, and the `unclosed` variant stay written out verbatim, because a builder clean enough to emit them would also hide the shape the assertion targets.
- `hidden_heading_single_name`: `HIDDEN_HEADING` is defined once, so the fenced parametrization can prove each of its four variants really carries a level-three heading line that a naive splitter would tear apart.
- `one_blank_line_between_blocks`: `rationale` joins blocks with a blank line and the blocks carry no trailing newline, so exactly one blank line separates two sections.

## Inbound Ports
- **Module API**: The fragment builders `section(title, body)`, `fenced(body, fence)`, `rationale(*blocks)`, and `sections(pairs)`, plus the fixture constants and variant maps.

## Outbound Ports
- None. The module consumes no ports.

## Data Contracts
- **`PROTOCOL_SECTIONS` / `NON_PROTOCOL_SECTIONS`**: tuples of `(title, body)` pairs. The protocol titles are the four the plan format defines, and the non-protocol titles are disjoint from them, which is what lets a test prove that an authored heading the format does not define still reaches the tree.
- **`FENCED_HEADING_RATIONALES`**: a mapping keyed by `backtick`, `tilde`, `longer`, and `unclosed`, each holding a rationale whose fenced block contains a level-three heading line.
- **`NON_SPLITTING_LINES`**: a mapping keyed by `four_hashes`, `indented`, and `numeric_marker`, each a body that must not open a section.

## Operations

### `section(title, body) -> str`
- **Postconditions:** Returns the level-three heading line for `title` followed by `body` verbatim, with no trailing newline.

### `fenced(body, fence) -> str`
- **Postconditions:** Returns `body` wrapped in an opener and a closer of the same sequence, so the block stays well formed for any legal fence, including a four-backtick opener. The default fence is three backticks.

### `rationale(*blocks) -> str`
- **Postconditions:** Returns the blocks joined by a blank line, leaving exactly one blank line between two of them because the blocks themselves carry no trailing newline.

### `sections(pairs) -> str`
- **Postconditions:** Returns consecutive sections rendered from the given `(title, body)` pairs in order.
