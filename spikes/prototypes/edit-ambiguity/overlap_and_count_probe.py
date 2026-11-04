"""Verdict probe: where the candidate count comes from, and overlap risk.

Two questions this probe answers empirically:

1. An indentation-only duplicate promotes both windows to 1.0, so the authored
   FIND appears zero times in the file while `best_match` appears twice. The
   count in the ambiguity message must therefore come from the candidate set or
   from `best_match`, never from `content.count(find)`.
2. The refined clause blocks a fuzzy winner when any second candidate clears the
   threshold. A single true location whose adjacent window is similar enough
   would be a false positive, so the shifted-start fixtures measure whether the
   runner-up can reach the threshold without real duplication.
"""

from __future__ import annotations

from rule_harness import install_recording_rule, last_decision
from scenarios import (
    fuzzy_handler_find,
    handler_block_file,
    handler_tail_duplicate_file,
    indented_duplicate_file,
    unindented_duplicate_find,
)
from teddy_executor.core.domain.models import MultipleMatchesFoundError
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.services.validation_rules.edit_matcher import find_best_match

THRESHOLD = 0.95


def _inspect(label: str, content: str, find: str) -> None:
    best_match, score, is_ambiguous, _ = find_best_match(content, find, THRESHOLD)
    decision = last_decision()
    refined = "AMBIGUOUS" if decision.ambiguous else "accepted"
    print(
        f"{label}: score={score:.4f} row_ambiguous={is_ambiguous} "
        f"top={decision.top:.4f} second={decision.second:.4f} "
        f"ties={decision.ties} candidates={decision.above_threshold} "
        f"count_find={content.count(find)} count_best={content.count(best_match)} "
        f"refined={refined}"
    )


def main() -> None:
    install_recording_rule()

    _inspect(
        "indentation_only_duplicate",
        indented_duplicate_file(),
        unindented_duplicate_find(),
    )
    _inspect(
        "repeated_inner_lines_single_location",
        handler_block_file(),
        fuzzy_handler_find(),
    )
    _inspect(
        "tail_duplicate_adjacent_start",
        handler_tail_duplicate_file(),
        fuzzy_handler_find(),
    )

    simulator = EditSimulator()
    try:
        simulator._apply_single_edit(
            indented_duplicate_file(),
            unindented_duplicate_find(),
            "    a = 3\n    b = 4\n    return a + b\n",
            THRESHOLD,
            False,
        )
        outcome = "accepted"
    except MultipleMatchesFoundError as error:
        outcome = getattr(error, "message", str(error))
    print(f"indentation_only_duplicate_executor_message: {outcome!r}")


if __name__ == "__main__":
    main()
