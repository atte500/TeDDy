"""Verdict probe: worst-case cost of refining every seeded large-block window.

The candidate evaluation cap keeps only the top five coarse-scored windows for
the refinement pass. For small find blocks the coarse pass already ran a full
difflib ratio per window and refinement reuses that score, so the cap saves no
work and only truncates the reported count. For large blocks the coarse pass
sub-samples and refinement recomputes a full ratio, so the cap is the only bound
on that recompute.

Removing the cap makes the ambiguity count exact. This probe measures the worst
realistic cost of that removal by scaling the number of large sibling blocks
that all clear the coarse filter, then timing refine-five against refine-all.
"""

from __future__ import annotations

import time
from typing import Tuple

import teddy_executor.core.services.validation_rules.edit_matcher as edit_matcher
from teddy_executor.core.services.validation_rules.edit_matcher import find_best_match

from rule_harness import install_recording_rule, last_decision

THRESHOLD = 0.95
CAP = edit_matcher.CANDIDATE_EVALUATION_CAP
UNLIMITED = 10**9


def _large_block(name: str, statements: int) -> str:
    """A block above LARGE_BLOCK_LINE_LIMIT so the coarse path sub-samples."""
    body = [f"    value_{i} = data[{i}] * factor + offset" for i in range(statements)]
    return "\n".join(
        [f"def {name}(data, factor, offset):", *body, "    return value_0"]
    ) + "\n"


def _cluster(count: int, statements: int) -> Tuple[str, str]:
    content = "\n".join(
        _large_block(f"compute_{i}", statements) for i in range(count)
    )
    # The FIND carries a def-line typo, so no window is verbatim and every
    # sibling block scores the same: the cap is forced to bind on a large pool.
    return content, _large_block("computa", statements)


def _run(content: str, find: str, cap: int):
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
        f"cap(refined={cap_refined} ambiguous={cap_amb} "
        f"ms={cap_s * 1000:.2f} score={cap_score:.2f}) | "
        f"full(refined={full_refined} ambiguous={full_amb} "
        f"ms={full_s * 1000:.2f} score={full_score:.2f})"
    )


def main() -> None:
    install_recording_rule()
    for count in (10, 30, 60, 100):
        content, find = _cluster(count, 30)
        _compare(f"{count}_large_blocks_def_typo", content, find)


if __name__ == "__main__":
    main()
