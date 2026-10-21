"""Verify the format-character fix through a parser normalizer replica.

Registers the patched replica under the production module name before the
parser chain is imported, so `parser_metadata` binds the replica's
`normalize_path` and `normalize_link_target`. Production code stays untouched.

Run: uv run python spikes/debug/read-validation-dotfile-path/03-verify-replica-fix.py
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

MODULE_NAME = "teddy_executor.core.services.parser_infrastructure"
REPLICA_PATH = Path(__file__).with_name("replica_parser_infrastructure.py")

spec = importlib.util.spec_from_file_location(MODULE_NAME, REPLICA_PATH)
if spec is None or spec.loader is None:
    raise SystemExit(f"cannot load replica from {REPLICA_PATH}")

replica = importlib.util.module_from_spec(spec)
sys.modules[MODULE_NAME] = replica

import teddy_executor.core.services as services_package

services_package.parser_infrastructure = replica
spec.loader.exec_module(replica)

# Imports below must follow the replica registration so parser_metadata binds
# the patched functions instead of the production originals.
from teddy_executor.adapters.outbound.local_file_system_adapter import (  # noqa: E402
    LocalFileSystemAdapter,
)
from teddy_executor.core.services import parser_metadata  # noqa: E402
from teddy_executor.core.services.markdown_plan_parser import (  # noqa: E402
    MarkdownPlanParser,
)
from teddy_executor.core.services.plan_validator import PlanValidator  # noqa: E402
from teddy_executor.core.services.validation_rules.filesystem import (  # noqa: E402
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
    # name, label, link target, expected resource, expected verdict
    ("plain-file-slash", "README.md", "/README.md", "README.md", "ACCEPTED"),
    ("dotfile-slash", ".gitignore", "/.gitignore", ".gitignore", "ACCEPTED"),
    ("dotfile-bare", ".gitignore", ".gitignore", ".gitignore", "ACCEPTED"),
    (
        "dotfile-zero-width",
        ".gitignore",
        "/\u200b.gitignore",
        ".gitignore",
        "ACCEPTED",
    ),
    (
        "zero-width-before-slash",
        ".gitignore",
        "\u200b/.gitignore",
        ".gitignore",
        "ACCEPTED",
    ),
    (
        "zero-width-mid-name",
        ".gitignore",
        ".\u200bgitignore",
        ".gitignore",
        "ACCEPTED",
    ),
)


def build_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="read-dotfile-replica-"))
    (root / "README.md").write_text("# probe\n", encoding="utf-8")
    (root / ".gitignore").write_text("logs/\n", encoding="utf-8")
    return root


def main() -> int:
    if parser_metadata.normalize_path is not replica.normalize_path:
        print("INVALID: parser_metadata did not bind the replica normalize_path.")
        return 2
    if parser_metadata.normalize_link_target is not replica.normalize_link_target:
        print("INVALID: parser_metadata did not bind the replica normalize_link_target.")
        return 2

    parser = MarkdownPlanParser()
    root = build_root()
    print(f"project root: {root}")
    print(f"files: {sorted(entry.name for entry in root.iterdir())}")
    print(f"replica module: {replica.__file__}\n")

    mismatches = 0
    for name, label, target, expected_resource, expected_verdict in VARIANTS:
        plan = parser.parse(PLAN_TEMPLATE.format(label=label, target=target))
        resource = plan.actions[0].params.get("resource")
        file_system = LocalFileSystemAdapter(
            edit_simulator=_UnusedEditSimulator(), root_dir=str(root)
        )
        validator = PlanValidator(
            file_system, validators=[ReadActionValidator(file_system)]
        )
        errors = validator.validate(plan)
        actual_verdict = "REJECTED" if errors else "ACCEPTED"

        ok = actual_verdict == expected_verdict and resource == expected_resource
        if not ok:
            mismatches += 1
        print(f"[{name}] {'PASS' if ok else 'FAIL'}")
        print(f"  plan target: {target!r}")
        print(f"  resource:    {resource!r} (expected {expected_resource!r})")
        print(f"  verdict:     {actual_verdict} (expected {expected_verdict})")
        for error in errors:
            print(f"  error: {error.message}")
        print()

    print(f"mismatched variants: {mismatches}/{len(VARIANTS)}")
    if mismatches:
        return 1
    print(
        "PROVEN: the replica normalizer strips invisible characters and every "
        "variant validates."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())