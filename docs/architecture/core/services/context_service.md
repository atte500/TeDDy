# Application Service: `ContextService`

**Status:** Implemented
**Introduced in:**
- [Slice 13: Implement `context` Command](../../slices/executor/13-context-command.md)
- [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)

## 1. Purpose

The `ContextService` is the application service responsible for orchestrating the gathering of project context. It implements the `IGetContextUseCase` inbound port and acts as the central coordinator, using various outbound ports to collect information and assemble it into a `ContextResult` data transfer object.

## 2. Used Outbound Ports

*   [`IFileSystemManager`](../ports/outbound/file_system_manager.md): To read `.gitignore`, `.teddyignore` and other context files, and to create the default `.teddy/global.context` if it's missing.
*   [`IRepoTreeGenerator`](../ports/outbound/repo_tree_generator.md): To generate the repository's file tree as a string.
*   [`IEnvironmentInspector`](../ports/outbound/environment_inspector.md): To gather information about the operating system and environment, including the user's shell.

## 3. Implemented Inbound Ports

*   [`IGetContextUseCase`](../ports/inbound/get_context_use_case.md)

## 4. Orchestration Logic

When the `get_context` method is called, the `ContextService` performs the following steps in order:
1.  It checks for the existence of `.teddy/global.context` using the `IFileSystemManager`.
2.  If the file does not exist, it instructs the `IFileSystemManager` to create it with the simplified default content (`README.md`, `docs/ARCHITECTURE.md`).
3.  It invokes the `IEnvironmentInspector` to get system information, ensuring the user's `shell` is included.
4.  It invokes the `IRepoTreeGenerator` to get the repository tree as a single string. The generator is responsible for respecting `.gitignore` and `.teddyignore` rules.
5.  It uses the `IFileSystemManager` to read the file paths from all `.teddy/*.context` files. These paths form the `context_vault_paths`.
6.  It uses the `IFileSystemManager` again to read the content of each file in `context_vault_paths`.
7.  It aggregates all collected data (system info, repo tree string, vault paths, file contents) into the `ContextResult` DTO and returns it.
