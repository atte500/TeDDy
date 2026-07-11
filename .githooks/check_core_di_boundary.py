#!/usr/bin/env python3
"""
Pre-commit hook: Verify no punq imports in core domain.

Scans each file passed as argument and exits with 1 if any file in
src/teddy_executor/core/ imports punq.
"""

import sys


def main() -> int:
    files = sys.argv[1:]
    if not files:
        return 0

    exit_code = 0
    for filepath in files:
        # Normalize to forward slashes for pattern matching
        normalized = filepath.replace("\\", "/")
        if "src/teddy_executor/core/" not in normalized:
            continue
        try:
            with open(filepath, encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("import punq") or stripped.startswith(
                        "from punq"
                    ):
                        print(
                            f"DI Boundary Violation: punq imported in core service ({filepath})."
                            " Core logic must not depend on DI framework."
                        )
                        exit_code = 1
        except OSError as e:
            print(f"Error reading {filepath}: {e}", file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
