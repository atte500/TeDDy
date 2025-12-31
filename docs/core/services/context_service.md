# Application Service: ContextService

**Motivating Vertical Slice:** [Implement `context` Command](../../slices/13-context-command.md)

## 1. Implemented Ports (Inbound)

*   [IGetContextUseCase](../ports/inbound/get_context_use_case.md)

## 2. Dependencies (Outbound Ports)

*   [IFileSystemManager](../ports/outbound/file_system_manager.md)
*   [IRepoTreeGenerator](../ports/outbound/repo_tree_generator.md)
*   [IEnvironmentInspector](../ports/outbound/environment_inspector.md)

## 3. Implementation Strategy

The `ContextService` is the central orchestrator for the `teddy context` command. It is responsible for gathering all pieces of information from its dependencies and assembling them into the final `ContextResult` domain object.

### `get_context()`

-   `**Status:**` Planned
-   **Logic:**
    1.  **Initialize `.teddy` Directory:** Use the `IFileSystemManager` to check for the existence of the `.teddy` directory and its contents (`.gitignore`, `context.json`, `permanent_context.txt`). If they don't exist, create them with their default content.
    2.  **Read Context File Lists:** Use the `IFileSystemManager` to read the file paths from `.teddy/context.json` and `.teddy/permanent_context.txt`.
    3.  **Gather Environmental Info:**
        a. Call `IEnvironmentInspector.get_environment_info()` to get OS and shell details.
        b. Call `IRepoTreeGenerator.generate_tree()` to get the repository file listing.
        c. Use `IFileSystemManager` to read the content of the root `.gitignore` file.
    4.  **Read File Contents:** Iterate through the combined list of file paths from the context files. For each path, use `IFileSystemManager.read_file()` to get its content. If a file is not found, the manager should signal this (e.g., return `None` or raise a specific, catchable error). Create a `FileContext` object for each file, capturing its path, content, and status (`"found"` or `"not_found"`).
    5.  **Assemble Result:** Construct the final `ContextResult` object, populating it with all the information gathered in the previous steps.
    6.  **Return Result:** Return the populated `ContextResult` object to the caller (the inbound adapter).
