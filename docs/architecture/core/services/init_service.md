# Component Design: InitService
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/services/init_service.py`](/src/teddy_executor/core/services/init_service.py)

## Purpose
Implements the `IInitUseCase` inbound port. It idempotently initializes a project by writing the `.teddy/` scaffolding, prompt files, and `docs/templates/` from bundled defaults, and it reports drift between user files and the bundled defaults.

## Consumers
- [`SessionService`](./session_service.md): Injects the init use case to ensure initialization before seeding context.
- [CLI Adapter](../../adapters/inbound/cli.md): Serves the `teddy init` and `teddy init templates` subcommands.
- [Composition Root](/src/teddy_executor/container.py): Registers `InitService` and binds it to `IInitUseCase`.

## Dependencies
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Creates directories, writes files, and reads bundled resources.

## Class Invariants
- `non_destructive_default`: No existing file is overwritten unless `overwrite` is `True`.
- `env_create_only`: `.teddy/.env` is written only when absent and is never overwritten, because it holds the non-regenerable API key.
- `stem_identity_prompts`: A prompt destination counts as present when any file shares its stem under any extension.
- `templates_explicit_only`: Bare `ensure_initialized` never creates `docs/templates/`; only `ensure_templates_initialized` does.

## Inbound Ports
- **`IInitUseCase`**: Exposes `ensure_initialized`, `ensure_prompts_initialized`, `ensure_config_initialized`, `ensure_templates_initialized`, and `check_drift`.

## Outbound Ports
- **`IFileSystemManager`**: The driven contract used for all file and directory operations.

## Data Contracts
- **`DriftReport`** (`teddy_executor.core.domain.models.drift_report`): Classifies prompt and template files as edited, missing, or clean.
- **`_CopyPolicy`** (frozen dataclass): Groups the optional copy behaviors `create_only` and `stem_identity`.
- **Template manifests:** `_TEMPLATE_FILES` and `_PROMPT_FILES` name the bundled defaults.

## Operations

### `ensure_initialized() -> str`
- **Preconditions:** None.
- **Postconditions:** Ensures `.teddy/` holds its config and prompt files and returns a summary string. It does not create `docs/templates/`.

### `ensure_prompts_initialized(overwrite=True) -> str`
- **Preconditions:** None.
- **Postconditions:** Ensures prompt files exist in `.teddy/prompts/`, overwriting when `overwrite` is `True` and removing stale same-stem files.

### `ensure_config_initialized(overwrite=True) -> str`
- **Preconditions:** None.
- **Postconditions:** Ensures `config.yaml`, `.gitignore`, `init.context`, and `.env` exist. `.env` is create-only.

### `ensure_templates_initialized(overwrite=False) -> str`
- **Preconditions:** None.
- **Postconditions:** Ensures the bundled templates exist in `docs/templates/`, overwriting only when `overwrite` is `True`.

### `check_drift() -> DriftReport`
- **Preconditions:** None.
- **Postconditions:** Returns a `DriftReport` comparing user prompts and templates against the bundled defaults.
