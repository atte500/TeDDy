"""Verdict probe: a fuzzy winner with a sibling clearing the threshold aborts."""

from __future__ import annotations

from rule_harness import install_refined_rule, last_decision
from scenarios import fuzzy_find, two_sibling_functions
from teddy_executor.core.services.validation_rules.edit import _validate_single_edit
from teddy_executor.core.services.validation_rules.edit_matcher import (
    find_best_match_and_diff,
)

THRESHOLD = 0.95


def _classify(errors) -> str:
    if not errors:
        return "success"
    message = errors[0].message.lower()
    if "ambiguous" in message:
        return "ambiguous"
    if "could not be located" in message:
        return "not_found"
    return "other"


def _probe(label: str, find_name: str) -> None:
    content = two_sibling_functions()
    find = fuzzy_find(find_name)
    _, score, is_ambiguous, _ = find_best_match_and_diff(
        content, find, threshold=THRESHOLD
    )
    decision = last_decision()
    errors = _validate_single_edit(
        {"find": find, "replace": "    return 0\n"},
        content,
        "sample.py",
        THRESHOLD,
        match_all=False,
    )
    print(
        f"{label}: ambiguous={is_ambiguous} validator={_classify(errors)} "
        f"score={score:.2f} top={decision.top:.4f} second={decision.second:.4f} "
        f"candidates_above_threshold={decision.above_threshold}"
    )


def main() -> None:
    install_refined_rule()
    _probe("near_tie_closer_to_alpha", "computa")
    _probe("near_tie_closer_to_beta", "compota")


if __name__ == "__main__":
    main()
