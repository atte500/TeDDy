# Application Service: `InitService`

**Status:** Refactoring

## 1. Purpose

The `InitService` is the application service responsible for the idempotent initialization of a TeDDy project. It implements the `IInitUseCase` port and centralizes the logic for creating the foundational directory structure, default templates, and user-editable prompt files. It supports a configurable template directory to ensure isolation in test environments. Changes are always non-destructive unless `overwrite=True` is explicitly passed.

## 2. Failure Modes

- **Resource Not Found**: If a bundled resource file (templates, prompts, config) is missing from the package, `_get_default_content()` returns `None`. This causes a skip, logged at DEBUG level. The init service MUST raise a clear error when MRP.xml is missing (as it is required for prompt assembly), but for other templates/config, missing resources are silently skipped.
- **Silent Error Swallowing (Known Debt)**: `_get_default_content()` catches `(OSError, yaml.YAMLError, ImportError, AttributeError)` and returns `None`. This can hide errors from Python version changes to `importlib.resources`. This is logged as Technical Debt for Milestone 4.

## 3. Class Invariants

- `_config_dir` is always a non-empty string pointing to the bundled config resource directory.
- `_file_system` is never None after initialization.
- The service MUST NOT modify or overwrite existing project files unless `overwrite=True` is explicitly passed.

## 4. Used Outbound Ports

*   [`FileSystemManager`](../ports/outbound/file_system_manager.md): To check for the existence of files and directories and to create them when missing.

## 5. Implemented Inbound Ports

*   [`IInitUseCase`](../ports/inbound/init.md)

## 6. Logic

### Initialization Logic (existing)

When `ensure_initialized` is called, the service performs the following checks and actions relative to the current working directory:

1.  **Directory Creation:** Checks for the `.teddy/` directory. If it does not exist, it is created.
2.  **Security Gate:** Checks for `.teddy/.gitignore`. If missing, it is created with a global ignore pattern (`*`) to prevent sensitive configuration from being accidentally committed to version control.
3.  **Default Configuration:** Checks for `.teddy/config.yaml`. If missing, it is created using bundled defaults.
4.  **Initial Context:** Checks for `.teddy/init.context`. If missing, it is created using bundled defaults.
5.  **Template Initialization (new):** Checks for `docs/templates/` directory. If missing, creates it and copies all bundled templates from `src/teddy_executor/resources/templates/`.

### Template Initialization Logic (new)

When `ensure_templates_initialized` is called, the service:

1.  Checks if `docs/templates/` directory exists. If not, creates it.
2.  Loads all files from `src/teddy_executor/resources/templates/` using `_get_default_content()` targeting the templates resource path.
3.  For each template file, copies it to `docs/templates/{filename}`. If `overwrite=True`, always overwrites; otherwise only writes missing files.
4.  Returns a human-readable status string.

### Template Files

The bundled templates directory contains 9 files:
- `specification-document.md` — Template for Specification Documents
- `task-brief.md` — Template for Task Briefs
- `case-file.md` — Template for Case Files
- `vertical-slice.md` — Template for Vertical Slices
- `milestone.md` — Template for Milestone documents
- `component-design.md` — Template for Component Design Documents
- `architecture.md` — Template for ARCHITECTURE.md Conventions section
- `project.md` — Template for PROJECT.md Roadmap section (references `docs/templates/makefile.md` as part of Milestone 0 foundational tasks)
- `makefile.md` — Makefile template for VCP commit and Remote Probing Protocol commands

## 7. Contracts / Methods

### `_init_templates(overwrite: bool = False) -> str`
- **Preconditions:** None. The service is initialized with a valid `_config_dir` pointing to the package resources.
- **Postconditions:** If the resource directory exists and contains template files, they are written to `docs/templates/` (create or overwrite based on `overwrite`). Returns a status string ("unchanged", "updated (N files)", or "overwritten (N files)").
- **Exceptions:** None. Missing resources are silently skipped (logged at DEBUG). File system errors propagate from `IFileSystemManager`.

### `ensure_templates_initialized(overwrite: bool = False) -> str`
- **Preconditions:** None.
- **Postconditions:** Delegates to `_init_templates()`. Returns a human-readable string prefixed with "Templates" (e.g., "Templates updated (9 files).").
- **Exceptions:** None.
- **Contract Dependencies:** Relies on `_get_default_content()` loading from `src/teddy_executor/resources/templates/`.

## 8. All operations are designed to be non-destructive; the service will never modify or overwrite an existing project file unless `overwrite=True`.
