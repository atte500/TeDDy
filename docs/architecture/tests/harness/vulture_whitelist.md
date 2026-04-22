# Component: Vulture Whitelist
- **Status:** Planned

## Purpose / Responsibility
The Vulture Whitelist module (`tests/harness/vulture_whitelist.py`) is a first-class citizen of the test harness. Its sole responsibility is to provide static usage of code that is called dynamically or implicitly by frameworks (like Textual or DI containers) to prevent false-positive "dead code" reports from Vulture.

## Ports
### Inbound
- **Vulture Runner:** Reads this file as part of its scanning paths.

### Outbound
- **Core Ports:** The whitelist imports and "calls" methods on these interfaces.
- **TUI Adapters:** The whitelist "uses" Textual message handlers (e.g., `on_mount`).

## Implementation Details / Logic
The module should be structured as a collection of "Usage Simulators". Each simulator function should take a relevant interface as an argument and invoke the methods that Vulture otherwise considers unused.

### Rules
1. **Valid Python:** The file MUST be valid Python and pass `mypy` and `ruff`.
2. **No Execution:** This file is never executed at runtime or during tests; it exists only for static analysis.
3. **Interface-Driven:** Favor using actual Port interfaces to protect abstract methods.
4. **Framework Handlers:** For Textual handlers, use a dummy class that inherits from the relevant base class to protect the standard handler names (`on_mount`, `compose`, etc.).

## Data Contracts / Methods
- `whitelist_textual_handlers()`: Simulates usage of standard Textual lifecycle methods.
- `whitelist_core_ports(ports: ActionPorts)`: Simulates usage of all methods across the core outbound ports.
