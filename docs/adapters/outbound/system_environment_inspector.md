# Outbound Adapter: SystemEnvironmentInspector

-   `**Status:**` Planned
-   **Motivating Vertical Slice:** [Implement `context` Command](../../slices/13-context-command.md)

This adapter is responsible for inspecting the local machine's environment to gather information such as OS type, shell, and Python version.

## 1. Implemented Ports

*   [IEnvironmentInspector](../../core/ports/outbound/environment_inspector.md)

## 2. Implementation Notes

The implementation will use Python's standard libraries (`platform`, `os`, `sys`), which require no external dependencies. A technical spike has verified that these modules provide a reliable, cross-platform way to retrieve the necessary information.

The adapter will handle common platform differences, such as checking for `COMSPEC` on Windows for the shell, to provide the most accurate information possible.

### `get_environment_info()`

-   `**Status:**` Planned
-   **Logic:**
    1.  Call `platform.system()` to get the OS name.
    2.  Check the `SHELL` environment variable for the user's shell on POSIX systems.
    3.  If on Windows, check the `COMSPEC` environment variable as a fallback.
    4.  Use `sys.version_info` to construct a clean `major.minor.micro` version string for the Python interpreter.
    5.  Return this information in a dictionary with keys `os`, `shell`, and `python_version`.

## 3. Verified Code Snippet (from Spike)

This snippet from the verification spike demonstrates the core logic for gathering the environment details.

```python
import os
import platform
import sys

def get_environment_details():
    """
    Gathers and returns a dictionary of key environment details.
    """
    os_name = platform.system()

    # Get current shell, with fallback for Windows.
    shell = os.environ.get('SHELL', 'N/A')
    if os_name == 'Windows':
        shell = os.environ.get('COMSPEC', 'cmd.exe')

    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    return {
        "os": os_name,
        "shell": shell,
        "python_version": py_version,
    }
```
