"""Looks-like probe: the ambiguity message at a precision that reveals ties.

The current validator message prints the two-decimal score, so a 0.9939 winner
and a 0.9879 runner-up both render as 0.99. This probe prints the message the
user would see today beside a proposed message that carries the candidate count
and the runner-up at four decimals, so the alignment gate can judge wording and
layout without building UI.
"""

from __future__ import annotations

import argparse

from rule_harness import install_refined_rule, last_decision
from scenarios import (
    DUPLICATE_BLOCK,
    duplicate_block_file,
    fuzzy_find,
    indented_duplicate_file,
    sibling_function,
    two_sibling_functions,
    unindented_duplicate_find,
)
from teddy_executor.core.services.validation_rules.edit import _validate_single_edit
from teddy_executor.core.services.validation_rules.edit_matcher import find_best_match
from teddy_executor.core.utils.markdown import embed_in_fence

THRESHOLD = 0.95
HINT = (
    "Please provide a larger FIND block to uniquely identify the section, "
    "refactor the code to avoid duplication. Alternatively you can use the "
    "list item `Match All: true` to change all occurrences in the file at once."
)


def _proposed_validator_message(
    path: str, find: str, decision, precision: int
) -> str:
    return (
        f"The `FIND` block is ambiguous in: {path}\n"
        f"**Similarity Score:** {decision.top:.{precision}f}\n"
        f"**Runner-up Score:** {decision.second:.{precision}f}\n"
        f"**Candidates Above Threshold:** {decision.above_threshold}\n"
        f"**FIND Block:**\n"
        f"{embed_in_fence(find, '')}\n"
        f"**Hint:** {HINT}"
    )


def _proposed_executor_message(find: str, decision, precision: int) -> str:
    return (
        f"Found {decision.above_threshold} ambiguous candidates for {find!r} "
        f"(best score {decision.top:.{precision}f}, "
        f"runner-up {decision.second:.{precision}f}). "
        f"Aborting edit to prevent ambiguity. {HINT}"
    )


def _show(label: str, content: str, find: str, precision: int) -> None:
    find_best_match(content, find, THRESHOLD)
    decision = last_decision()
    errors = _validate_single_edit(
        {"find": find, "replace": "# replaced\n"},
        content,
        "sample.py",
        THRESHOLD,
        match_all=False,
    )
    current = errors[0].message if errors else "success (no error raised)"
    print(
        f"=== {label} (top={decision.top:.{precision}f} "
        f"second={decision.second:.{precision}f} "
        f"candidates={decision.above_threshold}) ==="
    )
    print(f"--- refined rule, existing template ---\n{current}\n")
    print(
        f"--- proposed validator ---\n"
        f"{_proposed_validator_message('sample.py', find, decision, precision)}\n"
    )
    print(
        f"--- proposed executor ---\n"
        f"{_proposed_executor_message(find, decision, precision)}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--precision",
        type=int,
        default=4,
        help="Decimal places used for every reported score (default: 4).",
    )
    args = parser.parse_args()

    install_refined_rule()
    _show(
        "fuzzy_near_tie",
        two_sibling_functions(),
        fuzzy_find("computa"),
        args.precision,
    )
    _show(
        "verbatim_vs_near_duplicate",
        two_sibling_functions(),
        sibling_function("compute"),
        args.precision,
    )
    _show(
        "verbatim_duplicate",
        duplicate_block_file(),
        DUPLICATE_BLOCK,
        args.precision,
    )
    _show(
        "indentation_only_duplicate",
        indented_duplicate_file(),
        unindented_duplicate_find(),
        args.precision,
    )


if __name__ == "__main__":
    main()
