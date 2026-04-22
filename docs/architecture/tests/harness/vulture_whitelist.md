# Component: Vulture Whitelist
- **Status:** Implemented

## Purpose / Responsibility
The `vulture_whitelist` is a specialized test harness component designed to suppress false positives in dead-code detection while maintaining type-safe verification. It solves the problem of dynamic framework callbacks (like Textual's `on_mount` or Typer's CLI handlers) and abstract method parameters that appear "unused" to static analysis.

## Logic / Implementation
This component uses a **Hybrid Whitelist Strategy**:
1. **Python Whitelist:** A dedicated module (`tests/harness/vulture_whitelist.py`) that simulates usage of domain types, interfaces, and framework patterns. Because it uses actual imports and type-hints, `mypy` and `ruff` verify that the whitelist itself remains accurate as the codebase evolves. It uses `from __future__ import annotations` to ensure Vulture can track usage within type hints.
2. **TOML Suppression:** Generic, noisy parameter names (e.g., `path`, `text`, `reason`, `old_path`) are suppressed in `pyproject.toml` to avoid polluting the Python manifest with non-architectural noise.

## Usage in Quality Gates
- **Vulture:** Reads the whitelist to see "usage" of dynamic names.
- **Mypy:** Verifies that all types referenced in the whitelist exist and are correctly imported.
- **Ruff:** Exempts the whitelist from complexity rules (C901, PLR0915) to allow it to serve as a flat manifest of references.

## Maintenance Rule
When adding a new dynamic callback (e.g., a new Textual `action_*` method or a new Port interface), the Developer MUST add a corresponding simulation entry in `tests/harness/vulture_whitelist.py`.
