#!/usr/bin/env python3
"""Pre-commit hook: no un-isolated raw side-effecting CLI invocations in tests.

A test that drives a side-effecting CLI command (``init``, ``start``,
``resume``, ``execute``, ``context``) through ``typer.testing.CliRunner``
without changing the process CWD can leak real filesystem artifacts into the
repository root. The canonical case is ``runner.invoke(app, ["init"])``: a bare
``init`` unconditionally scaffolds ``.teddy/`` and ``docs/templates/`` via the
default ``LocalFileSystemAdapter(root_dir=".")``, whose root is resolved lazily
against the process CWD (this is the macOS-CI pollution defect class).

Raw unit-level ``runner.invoke(...)`` calls bypass the acceptance harness
(``tests/harness/drivers/cli_adapter.py::CliTestAdapter``), which isolates CWD by
calling ``monkeypatch.chdir(...)`` before every invocation. This hook flags,
within ``tests/`` (excluding ``tests/harness/``), a literal
``.invoke(app, ["<side-effecting>", ...])`` whose enclosing scope shows no
CWD-isolation signal.

A call is considered isolated when its enclosing scope contains a ``chdir``
call, or is explicitly opted out with the ``raw-cli-invoke-ok`` comment token.
``--help``/``-h`` invocations and non-literal argument lists are ignored.

Detection is AST-based so invoke calls embedded in string literals are never
false-positived. Exits with 1 if any violation is found.
"""

import ast
import sys
from collections.abc import Iterator

# Commands that write real scaffolding into the project root when the process
# CWD is the repo root. ``update`` / ``version`` are read-only w.r.t. the repo
# root and are deliberately excluded.
SIDE_EFFECTING_COMMANDS = frozenset({"init", "start", "resume", "execute", "context"})

# Help-only invocations have no side effects.
_HELP_FLAGS = frozenset({"--help", "-h"})

# Tokens whose presence anywhere in the enclosing scope marks it CWD-isolated.
_GUARD_TOKENS = ("chdir",)

# Explicit opt-out marker for a deliberate, reviewed raw invocation.
_OPT_OUT_MARKER = "raw-cli-invoke-ok"

# Minimum argument count for ``runner.invoke(target, args, ...)``.
_MIN_INVOKE_ARGS = 2


def _str_const(node: ast.AST) -> str | None:
    """Return the value if ``node`` is a string literal, else ``None``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _iter_candidates(tree: ast.AST) -> Iterator[ast.Call]:
    """Yield ``.invoke`` calls whose literal command is side-effecting."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "invoke"):
            continue
        if len(node.args) < _MIN_INVOKE_ARGS:
            continue
        args_node = node.args[1]
        if not isinstance(args_node, ast.List) or not args_node.elts:
            continue
        command = _str_const(args_node.elts[0])
        if command not in SIDE_EFFECTING_COMMANDS:
            continue
        if any(_str_const(elt) in _HELP_FLAGS for elt in args_node.elts):
            continue
        yield node


def _enclosing_function(
    node: ast.AST, parents: dict[int, ast.AST]
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    parent = parents.get(id(node))
    while parent is not None:
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return parent
        parent = parents.get(id(parent))
    return None


def _scope_lines(
    node: ast.AST, parents: dict[int, ast.AST], lines: list[str]
) -> list[str]:
    """Return the source lines of the innermost enclosing scope."""
    scope = _enclosing_function(node, parents)
    if scope is None:
        return lines
    start = scope.lineno
    for decorator in scope.decorator_list:
        start = min(start, decorator.lineno)
    end = scope.end_lineno or scope.lineno
    return lines[start - 1 : end]


def _is_isolated(node: ast.AST, parents: dict[int, ast.AST], lines: list[str]) -> bool:
    text = "\n".join(_scope_lines(node, parents, lines))
    if _OPT_OUT_MARKER in text:
        return True
    return any(token in text for token in _GUARD_TOKENS)


def check_file(filepath: str) -> list[str]:
    """Return a list of violation messages for the given Python file."""
    try:
        with open(filepath, encoding="utf-8") as handle:
            source = handle.read()
    except OSError as error:
        return [f"Error reading {filepath}: {error}"]

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as error:
        return [f"Error parsing {filepath}: {error}"]

    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    lines = source.splitlines()
    violations: list[str] = []
    for node in _iter_candidates(tree):
        if _is_isolated(node, parents, lines):
            continue
        violations.append(
            f"Unisolated side-effecting CLI invocation: {filepath}:{node.lineno}\n"
            "  Raw CliRunner.invoke(...) reaches a side-effecting command with no "
            "CWD isolation.\n"
            "  Add `monkeypatch.chdir(tmp_path)` (or use CliTestAdapter), or opt out "
            "with a `# raw-cli-invoke-ok` comment."
        )
    return violations


def main() -> int:
    files = sys.argv[1:]
    if not files:
        return 0

    exit_code = 0
    for filepath in files:
        normalized = filepath.replace("\\", "/")
        if (
            not normalized.startswith("tests/")
            or normalized.startswith("tests/harness/")
            or not normalized.endswith(".py")
        ):
            continue
        for message in check_file(filepath):
            print(message)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
