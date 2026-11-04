# Component Design: EditScenarios
- **Status:** Implemented
- **Source:** [`tests/harness/setup/edit_scenarios.py`](/tests/harness/setup/edit_scenarios.py)

## Purpose
Provides one source of truth for the canonical EDIT matcher scenarios: composable content builders and five named content/FIND bundles that matcher and validator tests read instead of re-authoring fixture text. The module is data only and imports nothing from `teddy_executor`.

## Consumers
- Matcher and validator unit tests (`tests/suites/unit/core/services/`): drive the refined ambiguity condition, the exact candidate count, and the ambiguity messages from the shared scenarios.
- Harness contract tests (`tests/suites/unit/test_edit_scenarios_harness.py`): pin each builder's shape and every bundle's content/FIND pairing.

## Dependencies
None — the module imports only `typing.NamedTuple` and holds no state.

## Class Invariants
- `data_only`: imports nothing from `teddy_executor`, so a scenario cannot couple a test to the implementation it exercises.
- `builder_purity`: every builder is deterministic and returns the same string for the same arguments.
- `bundle_pairing`: every bundle pairs the file content with the FIND block that drives it.

## Inbound Ports
None — a test-facing module of functions and module constants.

## Outbound Ports
None — no I/O and no injected dependencies.

## Data Contracts
- **`EditScenario`** (`NamedTuple`): `content: str`, `find: str`.
- **Builders**: `sibling_function(name)`, `two_sibling_functions(first="compute", second="compote")`, `fuzzy_find(name)`, `repeated_function(name, copies)`, `duplicate_block_file()`, `repeated_line_file()`, `fuzzy_repeated_line_find()`, `indented_duplicate_file()`, `unindented_duplicate_find()`, `handler_block_file()`, `handler_tail_duplicate_file()`, `fuzzy_handler_find()`.
- **Bundles**: `VERBATIM_VS_NEAR_DUPLICATE`, `FUZZY_NEAR_TIE`, `VERBATIM_DUPLICATE`, `INDENTATION_ONLY_DUPLICATE`, `REPEATING_INNER_LINE`.

## Operations

### `sibling_function(name) -> str`
- **Preconditions:** `name` is a string.
- **Postconditions:** Returns one accumulator function whose body is byte-identical across every name.
- **Exceptions:** None.

### `two_sibling_functions(first="compute", second="compote") -> str`
- **Preconditions:** Both names are strings.
- **Postconditions:** Returns two functions sharing one body, differing only in their def line.
- **Exceptions:** None.

### `repeated_function(name, copies) -> str`
- **Preconditions:** `copies` is a non-negative integer.
- **Postconditions:** Returns `copies` byte-identical blocks separated by blank lines, so every window ties exactly.
- **Exceptions:** None.
