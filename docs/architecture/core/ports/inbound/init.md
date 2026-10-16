# Component Design: IInitUseCase
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/ports/inbound/init.py`](/src/teddy_executor/core/ports/inbound/init.py)

## Purpose
Defines the inbound port that ensures a project carries the required TeDDy configuration, prompt, and template files. It is an abstract base class and is implemented by the `InitService`.

## Consumers
- [CLI Adapter](../../../adapters/inbound/cli.md): Invokes initialization before other commands and serves the `teddy init` subcommands.

## Dependencies
- **`DriftReport`** (`teddy_executor.core.domain.models.drift_report`): The return type of the drift check.

## Class Invariants
- `non_destructive_by_default`: Every ensure operation writes only missing files unless `overwrite` is `True`.

## Inbound Ports
- **`IInitUseCase`**: Exposes `ensure_initialized`, `ensure_prompts_initialized`, `ensure_config_initialized`, `ensure_templates_initialized`, and `check_drift`.

## Outbound Ports
None — the port declares no injected dependencies.

## Data Contracts
- **`DriftReport`** (`teddy_executor.core.domain.models.drift_report`): Enumerates edited or missing prompt and template files relative to the bundled defaults.

## Operations

### `ensure_initialized() -> str`
- **Postconditions:** Ensures the `.teddy/` directory and its config, ignore, context, and prompt files exist. Returns a human-readable summary. Existing files are never overwritten.

### `ensure_prompts_initialized(overwrite=False) -> str`
- **Postconditions:** Ensures prompt Markdown files exist in `.teddy/prompts/`. Overwrites only when `overwrite` is `True`.

### `ensure_config_initialized(overwrite=False) -> str`
- **Postconditions:** Ensures `config.yaml`, `.gitignore`, `init.context`, and `.env` exist in `.teddy/`. Overwrites only when `overwrite` is `True`.

### `ensure_templates_initialized(overwrite=False) -> str`
- **Postconditions:** Ensures Markdown templates exist in `docs/templates/`. Overwrites only when `overwrite` is `True`.

### `check_drift() -> DriftReport`
- **Postconditions:** Returns a `DriftReport` comparing user prompts and templates against the bundled defaults.
