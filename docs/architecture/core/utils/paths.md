# Component Design: Shared Path Utilities
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/utils/paths.py`](/src/teddy_executor/core/utils/paths.py)

## Purpose
A stateless module of pure helpers shared across the parser, the validation rules, and the session services. It single-sources the resource-path normalization pipeline and the rule that a pre-authored Markdown prompt wins over a stale sibling with the same stem.

## Consumers
- [`Parser Infrastructure`](../../core/services/parser_infrastructure.md): Imports `strip_format_characters` and applies it in both path normalizers.
- [`Plan Validator`](../../core/services/plan_validator.md): Reaches `normalize_resource_path` through the validation helpers, which compare a plan resource against the session and turn context lists.
- [`Session Service`](../../core/services/session_service.md): Delegates resource extraction to `normalize_resource_path`.
- [`Session Pruning Service`](../../core/services/session_pruning_service.md): Normalizes persisted resource paths before comparison.
- Prompt resolvers in [`Prompt Manager`](../../core/services/prompt_manager.md): Select a same-stem candidate through `prefer_markdown`.

## Dependencies
None. The module imports only the standard library (`re`, `unicodedata`, `pathlib`, `typing`).

## Class Invariants
- `stateless_pure_functions`: Every helper is a pure function of its arguments.
- `single_normalization_pipeline`: Markdown-link extraction, backslash conversion, the exact `./` prefix strip, the leading-slash strip, and format-character scrubbing run in one implementation, so consumers cannot drift apart.
- `hidden_file_preservation`: The `./` strip removes an exact two-character prefix only, so a leading dot on a hidden file survives.
- `format_character_scrubbing`: Invisible format characters are removed before any other step, so a path never names a different file than the one it displays. U+200C and U+200D stay because they shape adjacent glyphs.
- `markdown_prompt_precedence`: A `.md` candidate wins over every other extension with the same stem, regardless of directory listing order.

## Inbound Ports
None — this module is an internal helper surface.

## Outbound Ports
None — the module declares no injected dependencies.

## Data Contracts
- **Normalized resource path**: A POSIX-style string with no leading slash, no exact `./` prefix, no invisible format characters, and a preserved leading dot.
- **Prompt candidate**: Any value convertible to `Path`, returned unchanged from the input iterable.

## Operations

### `strip_format_characters(value) -> str`
- **Preconditions:** None.
- **Postconditions:** Returns the input without any Unicode `Cf` (format) codepoint except U+200C and U+200D, which shape adjacent glyphs.

### `normalize_resource_path(resource_str) -> str`
- **Preconditions:** None.
- **Postconditions:** Returns the Markdown-link target when the input is a link, otherwise the trimmed raw path. Both branches are scrubbed, slash-normalized, stripped of an exact `./` prefix, and stripped of a leading slash.

### `prefer_markdown(candidates) -> Optional[str | Path]`
- **Preconditions:** None.
- **Postconditions:** Returns the first candidate whose suffix is `.md`, else the first candidate, else `None` for an empty iterable.
