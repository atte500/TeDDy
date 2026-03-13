# Outbound Port: `ISystemEnvironment`

**Status:** Implemented

## 1. Purpose

The `ISystemEnvironment` port abstracts all interactions with the host operating system's environment, including file existence checks, temporary file management, environment variable access, and process execution. This ensures that services and adapters (like the `ConsoleInteractorAdapter`) remain pure and testable.

## 2. Port Contract

- `which(command: str) -> str | None`: Locates a command in the system PATH.
- `get_env(key: str, default: str | None = None) -> str | None`: Retrieves an environment variable.
- `run_command(args: list[str], check: bool = True, background: bool = False) -> None`: Executes an external command. Supports non-blocking background execution.
- `create_temp_file(suffix: str | None = None) -> str`: Creates a temporary file and returns its path.
- `delete_file(path: str) -> None`: Deletes a file from the system.
