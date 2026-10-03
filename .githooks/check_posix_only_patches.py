#!/usr/bin/env python3
"""Pre-commit hook: guard against unguarded POSIX-only symbol patches in tests.

POSIX-only attributes such as ``os.killpg`` do not exist on Windows. A test that
monkeypatches one without a platform guard raises ``AttributeError`` during SETUP
(``pytest``'s ``monkeypatch.setattr`` defaults to ``raising=True``) and turns the
windows-latest CI leg red even though the production code is platform-correct
(this is the Bug-61 defect class).

This hook flags, within ``tests/``:
  - ``monkeypatch.setattr(os, "<posix_only>", ...)``
  - ``monkeypatch.setattr("os.<posix_only>", ...)``
  - ``patch("os.<posix_only>", ...)``
  - ``patch.object(os, "<posix_only>", ...)``
(and the ``signal`` equivalents) unless the call is:
  - opted out with ``raising=False`` / ``create=True``, OR
  - guarded by a ``sys.platform`` condition (in-body ``pytest.skip`` guard, an
    enclosing ``if sys.platform`` wrapper, a ``skipif`` decorator, or a
    module-level ``pytestmark``), OR
  - guarded by a ``hasattr(os, ...)`` / ``getattr(os, ..., None)`` existence check.

Detection is AST-based so patch calls embedded in string literals are never
false-positived. Exits with 1 if any violation is found.
"""

import ast
import sys
from collections.abc import Iterator

# POSIX-only ``os`` members (CPython docs: "Availability: Unix"). Windows lacks
# all of these; ``os.kill``/``os.chmod``/``os.unlink`` DO exist on Windows and are
# deliberately excluded.
POSIX_ONLY_OS = frozenset(
    {
        "fork",
        "forkpty",
        "getegid",
        "geteuid",
        "getgid",
        "getgroups",
        "getpgid",
        "getpgrp",
        "getresgid",
        "getresuid",
        "getsid",
        "getuid",
        "chown",
        "chroot",
        "fchown",
        "initgroups",
        "killpg",
        "lchown",
        "nice",
        "setegid",
        "seteuid",
        "setgid",
        "setgroups",
        "setpgid",
        "setpgrp",
        "setresgid",
        "setresuid",
        "setsid",
        "setuid",
        "tcgetpgrp",
        "tcsetpgrp",
        "uname",
        "wait3",
        "wait4",
    }
)

# POSIX-only ``signal`` members (absent on Windows). ``signal.SIGINT`` exists on
# Windows and is deliberately excluded.
POSIX_ONLY_SIGNAL = frozenset(
    {
        "SIGALRM",
        "SIGCHLD",
        "SIGCONT",
        "SIGHUP",
        "SIGKILL",
        "SIGPIPE",
        "SIGQUIT",
        "SIGSTOP",
        "SIGTTIN",
        "SIGTTOU",
        "SIGUSR1",
        "SIGUSR2",
        "SIGWINCH",
    }
)

# Tokens whose presence anywhere in the enclosing scope marks it guarded.
_GUARD_TOKENS = ("sys.platform", "hasattr(os", "getattr(os,", "skipif")

# Minimum argument count for a ``setattr(target, name, ...)`` / ``patch.object``
# call to carry a target symbol (named to satisfy Ruff PLR2004).
_MIN_PATCH_ARGS = 2


def _posix_symbol(module: str, symbol: str) -> bool:
    if module == "os":
        return symbol in POSIX_ONLY_OS
    if module == "signal":
        return symbol in POSIX_ONLY_SIGNAL
    return False


def _str_const(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _module_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name) and node.id in ("os", "signal"):
        return node.id
    return None


def _split_target(target: str) -> tuple[str, str] | None:
    module, _, symbol = target.partition(".")
    if module and symbol:
        return module, symbol
    return None


def _resolve_setattr(args: list[ast.expr]) -> tuple[str | None, str | None]:
    """Resolve a ``setattr`` target to ``(module, symbol)`` for ``os``/``signal``."""
    if not args:
        return None, None
    # setattr(os|signal, "symbol", value)
    module = _module_name(args[0])
    if module and len(args) >= _MIN_PATCH_ARGS:
        symbol = _str_const(args[1])
        if symbol:
            return module, symbol
    # setattr("os.symbol", value)
    target = _str_const(args[0])
    if target:
        split = _split_target(target)
        if split:
            return split
    return None, None


def _iter_candidates(tree: ast.AST) -> Iterator[tuple[ast.Call, str, str]]:
    """Yield (call, module, symbol) for patch calls targeting POSIX-only symbols."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "setattr":
            module, symbol = _resolve_setattr(node.args)
            if module and symbol and _posix_symbol(module, symbol):
                yield node, module, symbol
        elif isinstance(func, ast.Name) and func.id == "patch":
            target = _str_const(node.args[0]) if node.args else None
            split = _split_target(target) if target else None
            if split and _posix_symbol(*split):
                yield node, split[0], split[1]
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == "object"
            and isinstance(func.value, ast.Name)
            and func.value.id == "patch"
            and len(node.args) >= _MIN_PATCH_ARGS
        ):
            module = _module_name(node.args[0])
            symbol = _str_const(node.args[1])
            if module and symbol and _posix_symbol(module, symbol):
                yield node, module, symbol


def _is_true(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _is_false(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _has_optout(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg == "raising" and _is_false(kw.value):
            return True
        if kw.arg == "create" and _is_true(kw.value):
            return True
    return False


def _mentions_platform(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Attribute)
            and sub.attr == "platform"
            and isinstance(sub.value, ast.Name)
            and sub.value.id == "sys"
        ):
            return True
    return False


def _enclosing_function(
    node: ast.AST, parents: dict[int, ast.AST]
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    parent = parents.get(id(node))
    while parent is not None:
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return parent
        parent = parents.get(id(parent))
    return None


def _is_guarded(node: ast.AST, parents: dict[int, ast.AST], lines: list[str]) -> bool:
    # 1. An enclosing ``if`` gated on sys.platform.
    parent = parents.get(id(node))
    while parent is not None:
        if isinstance(parent, ast.If) and _mentions_platform(parent.test):
            return True
        parent = parents.get(id(parent))

    # 2. A module-level ``pytestmark`` skipif guards every test in the file.
    module_text = "\n".join(lines)
    if "pytestmark" in module_text and "skipif" in module_text:
        return True

    # 3. A guard token anywhere in the enclosing function/module (in-body skip guard,
    #    skipif decorator, or a hasattr/getattr existence check).
    scope = _enclosing_function(node, parents)
    if scope is None:
        segment = lines
    else:
        start = scope.lineno
        for decorator in scope.decorator_list:
            start = min(start, decorator.lineno)
        end = scope.end_lineno or scope.lineno
        segment = lines[start - 1 : end]
    text = "\n".join(segment)
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
    for node, module, symbol in _iter_candidates(tree):
        if _has_optout(node) or _is_guarded(node, parents, lines):
            continue
        violations.append(
            f"Unguarded POSIX-only patch: {filepath}:{node.lineno}\n"
            f"  Patches POSIX-only symbol '{module}.{symbol}' with no platform guard.\n"
            '  Add `if sys.platform == "win32": pytest.skip(...)` (or '
            '`@pytest.mark.skipif(sys.platform == "win32", ...)`), or opt out '
            "with `raising=False` / `create=True`."
        )
    return violations


def main() -> int:
    files = sys.argv[1:]
    if not files:
        return 0

    exit_code = 0
    for filepath in files:
        normalized = filepath.replace("\\", "/")
        if not normalized.startswith("tests/") or not normalized.endswith(".py"):
            continue
        for message in check_file(filepath):
            print(message)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
