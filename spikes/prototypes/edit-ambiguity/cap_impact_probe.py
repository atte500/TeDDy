"""Verdict probe: what the candidate evaluation cap hides and what it costs.

`_evaluate_candidates` scores every seeded window, sorts by the coarse score,
and keeps only the top `CANDIDATE_EVALUATION_CAP` (5) for the refinement pass
that applies the indentation and substring promotions. This probe measures:

1. Where the cap binds: seeded windows versus windows that reach refinement.
2. Whether the cap changes the match or the ambiguity verdict.
3. What refining every seeded window costs, both for many small windows (the
   coarse pass already ran a full ratio per window) and for many large windows
   (the coarse pass sub-samples, so refinement recomputes the full ratio).
"""

from __future__ import annotations

import time
from typing import Tuple

import teddy_executor.core.services.validation_rules.edit_matcher as edit_matcher
from teddy_executor.core.services.validation_rules.edit_matcher import find_best_match

from rule_harness import install_recording_rule, last_decision
from scenarios import repeated_function, sibling_function

THRESHOLD = 0.95
CAP = edit_matcher.CANDIDATE_EVALUATION_CAP
UNLIMITED = 10**9


def _sibling_cluster(count: int) -> str:
    """`count` functions sharing a body, differing only in the def name.

    Every body line is a verbatim anchor found `count` times, so Tier 1 seeds
    one window per function and the cap is forced to bind.
    """
    return "\n".join(sibling_function(f"compute_{i}") for i in range(count))


def _large_block(name: str, statements: int) -> str:
    """A block longer than LARGE_BLOCK_LINE_LIMIT so the coarse path sub-samples."""
    body = [f"    value_{i} = data[{i}] * factor + offset" for i in range(statements)]
    return "\n".join(
        [f"def {name}(data, factor, offset):", *body, "    return value_0"]
    ) + "\n"


def _large_cluster(count: int, statements: int) -> Tuple[str, str]:
    content = "\n".join(_large_block(f"compute_{i}", statements) for i in range(count))
    return content, _large_block("computa", statements)


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
    cap_score, cap_ms, cap_amb, seeded, cap_refined = _run(content, find, CAP)
    full_score, full_ms, full_amb, _, full_refined = _run(content, find, UNLIMITED)
    print(
        f"{label}: seeded={seeded} "
        f"cap(refined={cap_refined} ambiguous={cap_amb} "
        f"ms={cap_ms * 1000:.2f} score={cap_score:.2f}) | "
        f"full(refined={full_refined} ambiguous={full_amb} "
        f"ms={full_ms * 1000:.2f} score={full_score:.2f})"
    )


def main() -> None:
    install_recording_rule()

    _compare(
        "seven_identical_small_blocks",
        repeated_function("compute", 7),
        sibling_function("computa"),
    )
    _compare(
        "forty_similar_small_blocks",
        _sibling_cluster(40),
        sibling_function("computa"),
    )

    large_content, large_find = _large_cluster(8, 30)
    _compare("eight_large_blocks_def_typo", large_content, large_find)

    two_large = _large_block("compute", 30) + "\n" + _large_block("compote", 30)
    _compare("two_large_blocks_verbatim", two_large, _large_block("compute", 30))
    _compare("two_large_blocks_def_typo", two_large, _large_block("computa", 30))


if __name__ == "__main__":
    main()
