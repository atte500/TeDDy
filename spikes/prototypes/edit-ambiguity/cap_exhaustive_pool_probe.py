"""Verdict probe: refine-all cost on the exhaustive (Tier 4) candidate pool.

Removing the refinement cap makes the reported candidate count exact. The worst
case measured so far is a large-block pool where every window clears the coarse
filter: 3.73 ms at 100 windows against 0.78 ms capped. One path stayed uncovered.
The exhaustive fallback seeds a window at EVERY start when no FIND line anchors
verbatim in the file and the first-line fuzzy cascade finds nothing. For small
find blocks refinement reuses the coarse score, so the added work is exactly one
promotion pass per seeded window. This probe measures that pass at scale.
"""

from __future__ import annotations

import time
from typing import Tuple

import teddy_executor.core.services.validation_rules.edit_matcher as edit_matcher
from teddy_executor.core.services.validation_rules.edit_matcher import find_best_match

from rule_harness import install_recording_rule, last_decision

THRESHOLD = 0.95
FIND_LINES = 20
CAP = edit_matcher.CANDIDATE_EVALUATION_CAP
UNLIMITED = 10**9


def _file_content(line_count: int) -> str:
    """Formulaic assignment lines, so no stripped line repeats."""
    return "".join(
        f"value_{i} = data[{i}] * factor + offset\n" for i in range(line_count)
    )


def _find_block() -> str:
    """Seeds the exhaustive tier by defeating both earlier tiers.

    Tier 1 anchors on stripped file lines, and no stripped FIND line equals any
    stripped file line, so it seeds nothing. Tier 2 needs the first FIND line to
    reach the threshold against some file line, which this block cannot. Tier 4
    therefore seeds a window at every valid start.
    """
    return "".join(
        f"result_{i} = transform(payload_{i}) - delta_{i}\n" for i in range(FIND_LINES)
    )


def _run(content: str, find: str, cap: int) -> Tuple[float, float, bool, int, int]:
    original = edit_matcher.CANDIDATE_EVALUATION_CAP
    edit_matcher.CANDIDATE_EVALUATION_CAP = cap
    try:
        start = time.perf_counter()
        _, score, is_ambiguous, _ = find_best_match(content, find, THRESHOLD)
        elapsed = time.perf_counter() - start
        decision = last_decision()
    finally:
        edit_matcher.CANDIDATE_EVALUATION_CAP = original
    return score, elapsed, is_ambiguous, decision.seeded, decision.refined


def _compare(label: str, content: str, find: str) -> None:
    cap_score, cap_s, cap_amb, seeded, cap_refined = _run(content, find, CAP)
    full_score, full_s, full_amb, _, full_refined = _run(content, find, UNLIMITED)
    print(
        f"{label}: seeded={seeded} "
        f"cap(refined={cap_refined} ambiguous={cap_amb} score={cap_score:.2f} "
        f"ms={cap_s * 1000:.2f}) | "
        f"full(refined={full_refined} ambiguous={full_amb} score={full_score:.2f} "
        f"ms={full_s * 1000:.2f}) "
        f"delta_ms={(full_s - cap_s) * 1000:.2f}"
    )


def main() -> None:
    install_recording_rule()
    find = _find_block()
    for line_count in (400, 800, 1600):
        _compare(
            f"{line_count}_line_file_exhaustive_pool",
            _file_content(line_count),
            find,
        )


if __name__ == "__main__":
    main()
