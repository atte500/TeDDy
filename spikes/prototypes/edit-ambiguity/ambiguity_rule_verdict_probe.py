"""Verdict probe: current tie rule versus the proposed refined rule."""

from __future__ import annotations

from rule_harness import install_recording_rule, last_decision
from scenarios import (
    DUPLICATE_BLOCK,
    duplicate_block_file,
    fuzzy_find,
    fuzzy_repeated_line_find,
    repeated_line_file,
    sibling_function,
    two_sibling_functions,
)
from teddy_executor.core.domain.models.plan import DEFAULT_SIMILARITY_THRESHOLD
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.services.validation_rules.edit_matcher import find_best_match

THRESHOLD = DEFAULT_SIMILARITY_THRESHOLD


def _verdict(label: str, content: str, find: str) -> None:
    _, score, is_ambiguous, _ = find_best_match(content, find, THRESHOLD)
    decision = last_decision()
    refined = "AMBIGUOUS" if decision.ambiguous else "accepted"
    print(
        f"{label}: score={score:.2f} old_ambiguous={is_ambiguous} "
        f"top={decision.top:.4f} second={decision.second:.4f} "
        f"ties={decision.ties} candidates_above_threshold={decision.above_threshold} "
        f"refined: {refined}"
    )


def main() -> None:
    install_recording_rule()

    _verdict(
        "verbatim_vs_near_duplicate",
        two_sibling_functions(),
        sibling_function("compute"),
    )
    _verdict("fuzzy_near_tie", two_sibling_functions(), fuzzy_find("computa"))
    _verdict("verbatim_duplicate", duplicate_block_file(), DUPLICATE_BLOCK)
    _verdict(
        "repeated_line_fuzzy_single_location",
        repeated_line_file(),
        fuzzy_repeated_line_find(),
    )

    simulator = EditSimulator()
    replaced, scores = simulator.simulate_edits(
        duplicate_block_file(),
        [{"find": DUPLICATE_BLOCK, "replace": "if ready:\n    process(items)\n"}],
        threshold=THRESHOLD,
        match_all=True,
    )
    print(
        "verbatim_duplicate_match_all: "
        f"remaining_finalize={replaced.count('finalize()')} "
        f"replacements={replaced.count('if ready:')} scores={scores}"
    )


if __name__ == "__main__":
    main()
