# Outbound Port: `IEnvironmentInspector`

- **Introduced in:** [Slice 13: Implement `context` Command](./../../../slices/13-context-command.md)
- **Consumer:** [ContextService](../../services/context_service.md)

This port defines the contract for a service that can inspect the local system to gather information about the operating system and terminal environment.

## Methods

### `get_os_info()`

- **Status:** Planned

#### Description
Retrieves information about the host operating system (e.g., "macOS 14.1", "Ubuntu 22.04 LTS", "Windows 11").

#### Postconditions
- **On Success:** Returns a `string` containing a description of the operating system.

---

### `get_terminal_info()`

- **Status:** Planned

#### Description
Retrieves information about the terminal or shell environment from which the command is being run (e.g., "zsh 5.9", "bash 5.1.16", "Windows Terminal").

#### Postconditions
- **On Success:** Returns a `string` containing a description of the terminal environment.
