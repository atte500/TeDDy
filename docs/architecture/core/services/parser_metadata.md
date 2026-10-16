# Component Design: Parser Metadata
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/parser_metadata.py`](/src/teddy_executor/core/services/parser_metadata.py)

## Purpose
A stateless module that extracts structured data from the Markdown lists and text blocks inside a plan: plan metadata, per-action metadata, environment lists, and handoff reference files.

## Consumers
- [`MarkdownPlanParser`](./markdown_plan_parser.md): Extracts top-level plan metadata and message content.
- [`Action Parser Strategies`](./action_parser_strategies.md): Extracts per-action metadata from the bulleted list.

## Dependencies
- [`parser_infrastructure`](./parser_infrastructure.md): Supplies `get_child_text`, `normalize_path`, `normalize_link_target`, and `find_node_in_tree`.
- `mistletoe` (external): Supplies the `List`, `ListItem`, `Link`, `Strong`, and `Emphasis` tokens matched during extraction; imports are lazy.

## Class Invariants
- `stateless_module`: Every function is a pure function of its arguments.
- `emphasis_preservation`: Value extraction preserves literal double underscores (for example `__main__.py`) that a plain text walk would collapse.
- `link_preferred_over_text`: A value linked as Markdown resolves through the link target before any plain-text fallback.

## Inbound Ports
None — this module is an internal helper of the parser subsystem.

## Outbound Ports
None — the module declares no injected dependencies.

## Data Contracts
- **Plan metadata** (`dict[str, str]`): Ordered key-value pairs parsed from the plan's metadata list.
- **Action metadata** (`tuple[Optional[str], dict[str, Any]]`): The description and the parameter map.
- **Environment map** (`dict[str, str]`): Key-value pairs parsed from a nested `env:` list.
- **Handoff reference files** (`list[str]`): Normalized paths collected from a `Reference Files:` or legacy `Handoff Resources:` list.

## Operations

### `parse_plan_metadata(metadata_list_node) -> dict[str, str]`
- **Preconditions:** The node is a Markdown list.
- **Postconditions:** Returns the top-level metadata map.

### `parse_action_metadata(metadata_list, link_key_map=None, text_key_map=None) -> tuple`
- **Preconditions:** The node is a Markdown list.
- **Postconditions:** Returns the action description and the parameter map, resolving linked keys before plain-text keys.

### `parse_env_from_metadata(metadata_list) -> Optional[dict[str, str]]`
- **Preconditions:** The node is a Markdown list.
- **Postconditions:** Returns the parsed environment map, or `None` when no `env:` entry is present.

### `parse_handoff_resources_from_list(metadata_list) -> Optional[list[str]]`
- **Preconditions:** The node is a Markdown list.
- **Postconditions:** Returns normalized reference-file paths, or `None` when absent.

### Internal helpers
`_extract_text_with_emphasis` and `_extract_value_after_key` recover value text without collapsing emphasis tokens. `_process_link_key` and `_process_text_key` resolve a single metadata key. `_find_all_links` collects every link in a subtree.
