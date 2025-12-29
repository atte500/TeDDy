# Inbound Port: `IGetContextUseCase`

- **Introduced in:** [slice-13-context-command](./../../../slices/13-context-command.md)

This port defines the contract for the application service responsible for gathering a comprehensive snapshot of the project's context.

## Methods

### `get_project_context()`

- **Status:** Planned

#### Description
Orchestrates the collection of all necessary project information, including environment details, repository structure, and the content of specified files. It returns this information aggregated into a single `ProjectContext` object.

#### Preconditions
- The application is running within a valid project directory.

#### Postconditions
- **On Success:** Returns a fully populated `ProjectContext` object as defined in the [Domain Model](../../domain_model.md).
- **On Failure:** Raises an exception if a critical, unrecoverable error occurs (e.g., inability to read the current working directory).
