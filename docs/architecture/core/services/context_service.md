# Application Service: `ContextService`

**Status:** Implemented
**Introduced in:**
- [Slice 13: Implement `context` Command](../../slices/executor/13-context-command.md)
- [Slice 17: Refactor `context` Command Output](../../slices/executor/17-refactor-context-command-output.md)

## 1. Purpose

The `ContextService` is the application service responsible for orchestrating the gathering of project context. It implements the `IGetContextUseCase` inbound port and acts as the central coordinator, using various outbound ports to collect information and assemble it into a `ProjectContext` data transfer object.

## 2. Used Outbound Ports

*   [`IFileSystemManager`](../ports/outbound/file_system_manager.md): To read `.gitignore`, `.teddyignore` and other context files.
*   [`IRepoTreeGenerator`](../ports/outbound/repo_tree_generator.md): To generate the repository's file tree as a string.
*   [`IEnvironmentInspector`](../ports/outbound/environment_inspector.md): To gather information about the operating system and environment, including the user's shell.

## 3. Implemented Inbound Ports

*   [`IGetContextUseCase`](../ports/inbound/get_context_use_case.md)

## 4. Orchestration Logic

When the `get_context` method is called, the `ContextService` performs the following steps in order:

1.  It invokes the `IEnvironmentInspector` to get system information, ensuring the user's `shell` is included.
2.  It invokes the `IRepoTreeGenerator` to get the repository tree as a single string. The generator is responsible for respecting `.gitignore` and `.teddyignore` rules.
3.  It uses the `IFileSystemManager` to read the file paths from all `.teddy/*.context` files. These paths form the `context_vault_paths`.
4.  It uses the `IFileSystemManager` again to read the content of each file in `context_vault_paths`.
5.  It formats the system information into a `header` string and the repository tree and file contents into a `content` string using private helper methods.
6.  It assembles the final `ProjectContext` DTO with the formatted `header` and `content` and returns it.

## 5. Data Contracts / Methods

### `get_context(context_files: Optional[Sequence[str]] = None) -> ProjectContext`

-   **Description:** Gathers project context information.
-   **Arguments:**
    -   `context_files`: (Optional) A list of specific `.context` files to read paths from. If `None`, the service defaults to reading all `.context` files in the `.teddy/` root (Standard/Manual mode).
-   **Returns:** A `ProjectContext` DTO containing the system info, repo tree, and resolved file contents.

## 6. Implementation Notes

-   **Context Configuration:** The `context` command's behavior is explicitly driven by the contents of `.teddy/*.context` files, providing a clear, user-configurable contract.
