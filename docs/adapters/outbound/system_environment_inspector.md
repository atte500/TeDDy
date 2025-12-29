# Outbound Adapter: `SystemEnvironmentInspectorAdapter`

- **Status:** Planned
- **Introduced in:** [Slice 13: Implement `context` Command](./../../../slices/13-context-command.md)

This adapter provides a concrete implementation of the `IEnvironmentInspector` port. It interacts directly with the underlying operating system via Python's standard library to fetch details about the OS and terminal environment.

## Implemented Ports
- [IEnvironmentInspector](../../core/ports/outbound/environment_inspector.md)

## Implementation Notes

### De-risking
A technical spike is not required. The necessary information can be reliably obtained using Python's built-in modules.

### Strategy

#### `get_os_info()`
This method will use the `platform` module to construct a descriptive string of the operating system. For example, `platform.system()`, `platform.release()`, and `platform.version()` can be combined to produce a result like `"macOS 14.1"` or `"Linux-5.15.0-78-generic-x86_64-with-glibc2.35"`.

#### `get_terminal_info()`
This method will inspect environment variables to determine the current shell. It will primarily check the `SHELL` environment variable on Unix-like systems. On Windows, it can check `COMSPEC`. The goal is to return a descriptive string like `"zsh 5.9"` or `"bash 5.1.16"`.

## External Documentation
- Python `platform` module: [https://docs.python.org/3/library/platform.html](https://docs.python.org/3/library/platform.html)
- Python `os` module (for environ): [https://docs.python.org/3/library/os.html](https://docs.python.org/3/library/os.html)
