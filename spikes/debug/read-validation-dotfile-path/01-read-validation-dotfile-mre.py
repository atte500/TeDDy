"""Guard READ validation against invisible format characters in a path.

Runs the real parser and the real pre-flight validator against a temporary
project root containing both a dotfile and an ordinary file. Every variant
prints the resource value in repr form, so invisible characters are visible.
A zero-width space inside a link target must resolve to the file it displays.

Run: uv run python spikes/debug/read-validation-dotfile-path/01-read-validation-dotfile-mre.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.services.plan_validator import PlanValidator
from teddy_executor.core.services.validation_rules.filesystem import (
    ReadActionValidator,
)


class _UnusedEditSimulator:
    """Satisfies the adapter constructor; READ never reaches the simulator."""

    def simulate_edits(self, content, edits, threshold=0.0, match_all=False):
        raise AssertionError("edit simulation is not part of this probe")


PLAN_TEMPLATE = """
# Read Probe
- **Status:** Green 🟢
- **Plan Type:** Test
- **Agent:** Test Agent

## Rationale
````text
Rationale.
````

## Action Plan
### `READ`
- **Resource:** [{label}]({target})
- **Description:** Read it
"""

VARIANTS = (
    # name, label, link target, expected verdict
    ("plain-file-slash", "README.md", "/README.md", "ACCEPTED"),
    ("dotfile-slash", ".gitignore", "/.gitignore", "ACCEPTED"),
    ("dotfile-bare", ".gitignore", ".gitignore", "ACCEPTED"),
    ("dotfile-relative", ".gitignore", "./.gitignore", "ACCEPTED"),
    ("dotfile-zero-width", ".gitignore", "/\u200b.gitignore", "ACCEPTED"),
)


def build_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="read-dotfile-probe-"))
    (root / "README.md").write_text("# probe\n", encoding="utf-8")
    (root / ".gitignore").write_text("logs/\n", encoding="utf-8")
    return root


def main() -> int:
    parser = MarkdownPlanParser()
    root = build_root()
    print(f"project root: {root}")
    print(f"files: {sorted(entry.name for entry in root.iterdir())}")
    print(f"python: {sys.version.split()[0]}\n")

    mismatches = 0

    for name, label, target, expected in VARIANTS:
        plan = parser.parse(PLAN_TEMPLATE.format(label=label, target=target))
        resource = plan.actions[0].params.get("resource")
        file_system = LocalFileSystemAdapter(
            edit_simulator=_UnusedEditSimulator(), root_dir=str(root)
        )
        validator = PlanValidator(
            file_system, validators=[ReadActionValidator(file_system)]
        )
        errors = validator.validate(plan)

        actual = "REJECTED" if errors else "ACCEPTED"
        exists = (
            file_system.path_exists(resource) if isinstance(resource, str) else None
        )
        if actual != expected:
            mismatches += 1
        print(f"[{name}] {actual} (expected {expected})")
        print(f"  plan target: {target!r}")
        print(f"  resource:    {resource!r}")
        print(f"  path_exists: {exists}")
        for error in errors:
            print(f"  error: {error.message}")
        print()

    print(f"mismatched variants: {mismatches}/{len(VARIANTS)}")
    if mismatches:
        return 1
    print(
        "CONFIRMED: every target validates, including the one carrying an "
        "invisible format character."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())