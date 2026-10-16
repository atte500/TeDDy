# Component Design: ReportParser
- **Status:** Implemented
- **Source:** [`tests/harness/observers/report_parser.py`](/tests/harness/observers/report_parser.py)

## Purpose
A test-harness observer that parses a Markdown execution report back into structured data. It is an inverse adapter: it reverses the report formatter so tests assert on typed fields instead of fragile string matching.

## Consumers
- [`CliTestAdapter`](../drivers/cli_adapter.md): Wraps the combined CLI output in a `ReportParser` from `execute_plan`.
- Acceptance and integration test suites: Assert on run summary, action logs, and resource contents.

## Dependencies
None — the parser uses only the Python standard library (`re`, `dataclasses`).

## Class Invariants
- `parse_on_construction`: `__init__` runs `_parse` immediately, so `run_summary`, `action_logs`, and `resource_contents` are populated before any access.
- `section_split`: Sections are isolated by splitting on the `## ` heading prefix.
- `lenient_status_match`: The action status is read case-insensitively across template variants.

## Inbound Ports
None — this is a test harness component.

## Outbound Ports
None — this is a test harness component.

## Data Contracts
- **`ActionLogEntry`** (dataclass): `type: str`, `status: str`, `params: Dict[str, str]`, `details: Dict[str, Any]`.
- **`run_summary`** (`Dict[str, str]`): The parsed summary key-value pairs.
- **`action_logs`** (`List[ActionLogEntry]`): The parsed per-action outcomes.
- **`resource_contents`** (`Dict[str, str]`): The parsed resource blocks keyed by path.

## Operations

### `ReportParser(content)`
- **Postconditions:** Parses `content` into `run_summary`, `action_logs`, and `resource_contents`.

### `stdout -> str`
- **Postconditions:** Returns the raw Markdown content.

### `summary -> Dict[str, str]`
- **Postconditions:** Returns the parsed summary fields.

### `extract_resource_contents() -> Dict[str, str]`
- **Postconditions:** Returns the parsed resource-contents mapping.

### `action_was_successful(index) -> bool`
- **Postconditions:** Returns `True` when the action at `index` carries status `SUCCESS`; returns `False` for an out-of-range index.

### Internal helpers
`_parse` orchestrates section extraction. `_parse_action_logs` and `_parse_action_chunk` build the per-action records. `_parse_resource_contents` extracts fenced resource blocks. `_extract_params_and_details`, `_apply_subject_to_params`, and `_extract_content_blocks` map headings and metadata into the structured fields.
