# Outbound Port: `IRepoTreeGenerator`

- **Introduced in:** [Slice 13: Implement `context` Command](./../../../slices/13-context-command.md)
- **Consumer:** [ContextService](../../services/context_service.md)

This port defines the contract for a service that can scan the project directory and generate a string representation of its file tree.

## Methods

### `generate_tree()`

- **Status:** Planned

#### Description
Scans the current project directory and produces a multi-line string that visually represents the file and directory structure. The implementation of this method **must** respect the ignore patterns found in the project's root `.gitignore` file.

#### Preconditions
- A `.gitignore` file may or may not exist at the project root.

#### Postconditions
- **On Success:** Returns a `string` containing the formatted repository tree.
- **On Failure:** Raises an appropriate exception if the directory cannot be scanned.
