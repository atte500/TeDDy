"""Verdict probe: the fuzzy ambiguity count must reflect the real candidates."""

from __future__ import annotations

from rule_harness import install_refined_rule, last_decision
from scenarios import fuzzy_find, repeated_function
from teddy_executor.core.domain.models import MultipleMatchesFoundError
from teddy_executor.core.services.edit_simulator import EditSimulator

THRESHOLD = 0.95


def main() -> None:
    install_refined_rule()
    simulator = EditSimulator()
    find = fuzzy_find("computa")

    for copies in (2, 3, 5, 7):
        content = repeated_function("compute", copies)
        try:
            simulator._apply_single_edit(
                content, find, "    return 0\n", THRESHOLD, False
            )
            outcome = "accepted"
        except MultipleMatchesFoundError as error:
            outcome = getattr(error, "message", str(error))
        decision = last_decision()
        print(
            f"copies={copies} seeded={decision.seeded} "
            f"refined={decision.refined} "
            f"refined_ambiguous={decision.ambiguous} "
            f"refined_candidates={decision.above_threshold} "
            f"true_occurrences={content.count('def compute(')} "
            f"old_message={outcome!r}"
        )


if __name__ == "__main__":
    main()
