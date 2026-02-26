**Status:** Planned
**Introduced in:** [Slice: Refactor `CommandResult` to `ShellOutput`](/docs/project/slices/14-refactor-commandresult-to-shelloutput.md)

## 1. Purpose / Responsibility

`ShellOutput` is a strictly-typed data structure that represents the complete result of a shell command execution. It serves as a data transfer object (DTO) to ensure that information about `stdout`, `stderr`, and the command's `return_code` is passed consistently and predictably from the shell execution adapter to any consuming service.

## 2. Ports

This component is a domain model (Value Object, specifically a DTO) and does not directly implement or use any ports. It is the data contract for the `IShellExecutor` outbound port.

## 3. Implementation Details / Logic

`ShellOutput` will be implemented as a `TypedDict`. This choice provides static type checking benefits with minimal runtime overhead, making it ideal for a simple data container.

## 4. Data Contracts / Methods

### `ShellOutput(TypedDict)`

| Key           | Type   | Description                                         |
| ------------- | ------ | --------------------------------------------------- |
| `stdout`      | `str`  | The standard output captured from the command.      |
| `stderr`      | `str`  | The standard error captured from the command.       |
| `return_code` | `int`  | The exit code of the command (0 for success).       |

- **Preconditions:** None.
- **Postconditions:** An instance of `ShellOutput` will always contain all three keys with their specified types.
- **Invariants:** The data is immutable once created.
- **Exception/Error States:** None.
