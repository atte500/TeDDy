# Outbound Adapter: `SystemEnvironmentInspector`

**Status:** Implemented
**Language:** Python 3.9+
**Introduced in:** [Slice 13: Implement `context` Command](../../slices/13-context-command.md)

## 1. Purpose

The `SystemEnvironmentInspector` is a simple adapter that implements the `IEnvironmentInspector` port. It uses Python's standard library modules (`os`, `platform`, `sys`) to gather information about the host system.

## 2. Implemented Outbound Port

*   [`IEnvironmentInspector`](../../core/ports/outbound/environment_inspector.md)

## 3. Dependencies

*   None (uses only Python standard library).

## 4. Implementation Details

The adapter calls functions like `platform.system()`, `platform.release()`, `sys.version`, `os.getcwd()`, and `os.getenv("SHELL")` to populate a dictionary with the required environment information. This adapter directly interacts with the underlying operating system via the Python runtime.
