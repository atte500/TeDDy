# Application Service: `InitService`

**Status:** Implemented

## 1. Purpose

The `InitService` is the application service responsible for the idempotent initialization of a TeDDy project. It implements the `IInitUseCase` port and centralizes the logic for creating the foundational directory structure and default templates. It supports a configurable template directory to ensure isolation in test environments.

## 2. Used Outbound Ports

*   [`FileSystemManager`](../ports/outbound/file_system_manager.md): To check for the existence of files and directories and to create them when missing.

## 3. Implemented Inbound Ports

*   [`IInitUseCase`](../ports/inbound/init.md)

## 4. Initialization Logic

When `ensure_initialized` is called, the service performs the following checks and actions relative to the current working directory:

1.  **Directory Creation:** Checks for the `.teddy/` directory. If it does not exist, it is created.
2.  **Security Gate:** Checks for `.teddy/.gitignore`. If missing, it is created with a global ignore pattern (`*`) to prevent sensitive configuration from being accidentally committed to version control.
3.  **Default Configuration:** Checks for `.teddy/config.yaml`. If missing, it is created using the `DEFAULT_CONFIG_YAML` template (containing LLM settings placeholders).
4.  **Initial Context:** Checks for `.teddy/init.context`. If missing, it is created using the `DEFAULT_INIT_CONTEXT` template (containing initial file paths for context gathering).

All operations are designed to be non-destructive; the service will never modify or overwrite an existing project file.
