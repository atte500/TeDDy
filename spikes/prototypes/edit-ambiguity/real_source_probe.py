"""Verdict probe: the refined clause against real source, not fixtures.

The slice claims Tier 1 exact anchoring keeps the blast radius narrow: on real
source with an injected one-character typo, every probe seeded a single
candidate. That claim is the only reason the new clause is safe to ship, and it
was measured on synthetic fixtures. This probe extracts real functions from the
project's own modules by AST and re-measures it verbatim and with a
one-character slip in the def line.
"""

from __future__ import annotations

import ast
from pathlib import Path

from rule_harness import install_recording_rule, last_decision
from teddy_executor.core.services.validation_rules.edit_matcher import find_best_match

THRESHOLD = 0.95
ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = [
    (
        "src/teddy_executor/core/services/validation_rules/edit_matcher.py",
        "_calculate_sub_sample_score",
    ),
    (
        "src/teddy_executor/core/services/validation_rules/edit_matcher.py",
        "_apply_indentation_bonus",
    ),
    (
        "src/teddy_executor/core/services/validation_rules/edit_matcher.py",
        "_refine_and_select_best",
    ),
    (
        "src/teddy_executor/core/services/validation_rules/edit.py",
        "_get_already_applied_hint",
    ),
    (
        "src/teddy_executor/core/services/edit_simulator.py",
        "_align_terminator",
    ),
    (
        "src/teddy_executor/core/services/edit_simulator.py",
        "_apply_indent_offset",
    ),
]


def extract_function(relative_path: str, name: str) -> str:
    """Slice a real function or method out of its module by AST line range.

    `ast.walk` reaches definitions nested in a class body, which iterating
    `ast.parse(...).body` does not, so class methods are addressable too.
    """
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "".join(lines[node.lineno - 1 : node.end_lineno])
    raise SystemExit(f"{name} not found in {relative_path}")


def def_typo(name: str) -> str:
    """Drop the last character of the function name, as a one-character slip."""
    return name[:-1]


def _report(label: str, content: str, find: str) -> None:
    best_match, score, is_ambiguous, _ = find_best_match(content, find, THRESHOLD)
    decision = last_decision()
    refined = "AMBIGUOUS" if decision.ambiguous else "accepted"
    print(
        f"{label}: score={score:.4f} row_ambiguous={is_ambiguous} "
        f"top={decision.top:.4f} second={decision.second:.4f} "
        f"seeded={decision.seeded} refined={decision.refined} "
        f"candidates={decision.above_threshold} "
        f"count_best={content.count(best_match)} refined={refined}"
    )


def main() -> None:
    install_recording_rule()
    for relative_path, name in SCENARIOS:
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        function = extract_function(relative_path, name)
        _report(f"{name} exact", content, function)
        _report(
            f"{name} def_typo",
            content,
            function.replace(name, def_typo(name), 1),
        )


if __name__ == "__main__":
    main()
