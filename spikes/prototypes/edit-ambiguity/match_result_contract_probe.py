"""Verdict probe: surface the runner-up without breaking existing callers."""

from __future__ import annotations

from typing import NamedTuple

import teddy_executor.core.services.validation_rules.edit_matcher as edit_matcher

from rule_harness import install_recording_rule, last_decision
from scenarios import fuzzy_find, two_sibling_functions


class MatchResult(NamedTuple):
    match: str
    score: float
    is_ambiguous: bool
    offset: int
    runner_up: float = 0.0
    candidate_count: int = 0


def find_best_match_ex(
    content: str, find: str, threshold: float = 0.95
) -> MatchResult:
    match, score, is_ambiguous, offset = edit_matcher.find_best_match(
        content, find, threshold
    )
    decision = last_decision()
    return MatchResult(
        match,
        score,
        is_ambiguous,
        offset,
        decision.second,
        decision.above_threshold,
    )


def main() -> None:
    install_recording_rule()
    content = two_sibling_functions()
    find = fuzzy_find("computa")

    result = find_best_match_ex(content, find)
    print(
        f"dto: score={result.score:.2f} ambiguous={result.is_ambiguous} "
        f"runner_up={result.runner_up:.4f} "
        f"candidate_count={result.candidate_count}"
    )

    try:
        match, score, is_ambiguous, offset = result
    except ValueError as error:
        print(f"namedtuple_four_way_unpack: ValueError: {error}")

    match, score, is_ambiguous, offset = edit_matcher.find_best_match(content, find)
    print(
        f"legacy_four_way_unpack: score={score:.2f} "
        f"ambiguous={is_ambiguous} offset={offset}"
    )


if __name__ == "__main__":
    main()
