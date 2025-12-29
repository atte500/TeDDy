# Application Service: `ContextService`

- **Introduced in:** [slice-13-context-command](./../../../slices/13-context-command.md)

This service is the central orchestrator for the `context` command's use case. It gathers all required information by calling various outbound ports and aggregates it into a `ProjectContext` domain object.

## Implemented Ports
- [IGetContextUseCase](../ports/inbound/get_context_use_case.md)

## Dependencies (Outbound Ports)
- `IFileSystemManager`: To handle all interactions with the local file system (reading/writing files, checking for directories).
- `IRepoTreeGenerator`: To generate the text-based representation of the repository file tree.
- `IEnvironmentInspector`: To gather information about the operating system and terminal environment.

## Implementation Strategy

### `get_project_context()`
- **Status:** Planned

This method will execute the following logic:

1.  **Initialize Context Directory:**
    -   Use the `IFileSystemManager` to check for the existence of the `.teddy` directory.
    -   If it does not exist, use the `IFileSystemManager` to create it.
    -   Use the `IFileSystemManager` to ensure the default files (`.teddy/context.yaml`, `.teddy/permanent_context.yaml`, `.teddy/.gitignore`) exist with their initial content.

2.  **Gather Environment Information:**
    -   Call the `IEnvironmentInspector` to get OS and terminal details.

3.  **Generate and Save Repository Tree:**
    -   Call the `IRepoTreeGenerator` to generate the file tree string. This port's implementation will be responsible for respecting the root `.gitignore`.
    -   Use the `IFileSystemManager` to write the resulting string to `repotree.log`.

4.  **Read Context Files and Aggregate Paths:**
    -   Use the `IFileSystemManager` to read the contents of `.teddy/context.yaml` and `.teddy/permanent_context.yaml`.
    -   Parse the YAML from both files to create a single, de-duplicated list of file paths to include in the context.

5.  **Read File Contents:**
    -   Instantiate a new `ProjectContext` domain object.
    -   Iterate through the aggregated list of file paths. For each path:
        -   Use the `IFileSystemManager` to read the file's content.
        -   If the file is read successfully, call `ProjectContext.add_file_content()` with the path, content, and a status of `'found'`.
        -   If the file cannot be read (e.g., does not exist), call `ProjectContext.add_file_content()` with the path, `null` content, and a status of `'not_found'`.
    -   Also read the root `.gitignore` and add its content to the `ProjectContext`.

6.  **Return Result:**
    -   Return the populated `ProjectContext` object.
