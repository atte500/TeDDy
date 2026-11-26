#!/usr/bin/env python3
"""
Pre-commit hook: Keep every money format inside `format_cost_usd`.

The terminal telemetry line, the guardrail limit notice, and the reviewer's
Context row all answer "what has this session cost?", so a second hand-written
dollar format is how three surfaces begin stating three different figures for
one session. This check fails on an f-string that renders a dollar amount with a
float format spec outside `core/utils/money.py`, the one module allowed to
render money.

Exits with 1 if any violation is found.
"""

import re
import sys

PACKAGE_PREFIX = "src/"
MONEY_RENDERER_SUFFIX = "core/utils/money.py"

# A dollar sign immediately followed by an interpolation whose format spec ends
# in `f`, as in f"${cost:.4f}". Token renders end in `k` (f"{n / 1000.0:.1f}k")
# and ${VAR} templates carry no format spec, so neither form is matched.
_DOLLAR_FLOAT_FORMAT = re.compile(r"""f["'][^"']*\$\{[^}]*:[^}]*f\}""")


def normalize_path(filepath: str) -> str:
    """Normalize a hook-supplied path so a `./` prefix cannot dodge a gate."""
    normalized = filepath.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_scanned_path(filepath: str) -> bool:
    """Whether the path is a production module this check inspects at all."""
    return normalize_path(filepath).startswith(PACKAGE_PREFIX)


def is_money_renderer(filepath: str) -> bool:
    """Whether the path is the one module allowed to render money."""
    return normalize_path(filepath).endswith(MONEY_RENDERER_SUFFIX)


def violations_in_lines(lines: list[str], filepath: str) -> list[str]:
    """Return one violation message per hand-written dollar format in `lines`."""
    violations: list[str] = []
    for lineno, line in enumerate(lines, start=1):
        if line.strip().startswith("#"):
            continue
        if _DOLLAR_FLOAT_FORMAT.search(line):
            violations.append(
                f"Money Rendering Violation: hand-written dollar format in "
                f"{filepath}:{lineno}\n"
                f"  {line.rstrip()}\n"
                f"  Route the amount through format_cost_usd from core/utils/money.py."
            )
    return violations


def check_file(filepath: str) -> list[str]:
    """Check a single file for violations. Returns list of error messages."""
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        return [f"Error reading {filepath}: {e}"]

    return violations_in_lines(lines, filepath)


def main() -> int:
    """Scan the supplied production modules, skipping the one money renderer."""
    files = sys.argv[1:]
    if not files:
        return 0

    exit_code = 0
    for filepath in files:
        if not is_scanned_path(filepath) or is_money_renderer(filepath):
            continue
        violations = check_file(filepath)
        if violations:
            for msg in violations:
                print(msg)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
