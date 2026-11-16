#!/usr/bin/env python3
"""Verify architectural layer boundaries and spikes/ isolation via AST."""

import ast
import sys

_FORBIDDEN_CORE_INTERNAL_PREFIXES = (
    "teddy_executor.adapters",
    "teddy_executor.registries",
    "teddy_executor.container",
)
_FORBIDDEN_CORE_ADAPTER_LIBS = frozenset(
    {
        "bs4",
        "ddgs",
        "httpx",
        "litellm",
        "prompt_toolkit",
        "pyperclip",
        "requests",
        "subprocess",
        "textual",
        "trafilatura",
        "typer",
        "yaml",
    }
)


def _iter_imported_modules(tree: ast.AST) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def _check_file(filepath: str) -> list[str]:
    normalized = filepath.replace("\\", "/")
    is_core = "src/teddy_executor/core/" in normalized
    is_production_or_test = normalized.startswith(("src/", "scripts/", "tests/"))
    if not (is_core or is_production_or_test):
        return []

    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=filepath)
    violations: list[str] = []

    for mod in _iter_imported_modules(tree):
        root = mod.split(".")[0]
        if is_production_or_test and root == "spikes":
            violations.append(f"{filepath}: forbidden import from spikes ({mod}).")
        if is_core and mod.startswith(_FORBIDDEN_CORE_INTERNAL_PREFIXES):
            violations.append(f"{filepath}: core must not import outer layer ({mod}).")
        if is_core and root in _FORBIDDEN_CORE_ADAPTER_LIBS:
            violations.append(
                f"{filepath}: core must not import adapter library ({mod})."
            )
    return violations


def main() -> int:
    exit_code = 0
    for filepath in sys.argv[1:]:
        try:
            for msg in _check_file(filepath):
                print(f"Architecture Boundary Violation: {msg}")
                exit_code = 1
        except (OSError, SyntaxError) as e:
            print(f"Error inspecting {filepath}: {e}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
