"""Verdict probe: can the cap or the sub-sample filter hide a large-block match?

Above `LARGE_BLOCK_LINE_LIMIT` the coarse pass scores each window with
`_calculate_sub_sample_score`, keeps only windows at or above
`SUB_SAMPLE_PASS_THRESHOLD`, and then the candidate cap keeps the top five of
those for the full-ratio refinement. For small find blocks the cap only
truncates the reported count. For large blocks the filter — not the cap —
bounds the refinement pool, so retiring the cap can only make the count exact
if the filter never discards a viable window.

Two scenarios answer that:

1. A 30-line FIND whose first line differs from two otherwise identical file
   regions. Both windows score 0.9667, so the pool holds two above-threshold
   candidates and the cap binds on the large path.
2. A 30-line FIND sharing no line with a 1600-line file, forcing the exhaustive
   tier. Every valid start is scanned with both the sub-sample score and the
   true full ratio, so the highest discarded full ratio is measured directly.
"""

from __future__ import annotations

import difflib
import time
from typing import List, Tuple

import teddy_executor.core.services.validation_rules.edit_matcher as edit_matcher
from teddy_executor.core.services.validation_rules.edit_matcher import (
    CANDIDATE_EVALUATION_CAP,
    SUB_SAMPLE_PASS_THRESHOLD,
    _calculate_sub_sample_score,
    find_best_match,
)

from rule_harness import install_recording_rule, last_decision

THRESHOLD = 0.95
UNLIMITED = 10**9
FIND_LINES = 30
FILE_LINES = 1600


def _large_find() -> List[str]:
    return [
        f"result_{i} = transform(payload_{i}) - delta_{i}\n"
        for i in range(FIND_LINES)
    ]


def _filler(count: int, tag: str) -> List[str]:
    return [f"{tag}_{i} = step_{i} + 1\n" for i in range(count)]


def _near_duplicate_file(find: List[str], copies: int) -> str:
    """`copies` regions matching every FIND line except the first."""
    lines = _filler(300, "head")
    for copy in range(copies):
        lines.append(find[0].replace("result_0", f"outcome_{copy}"))
        lines.extend(find[1:])
        lines.extend(_filler(300, f"mid_{copy}"))
    lines.extend(_filler(300, "tail"))
    return "".join(lines)


def _disjoint_file() -> str:
    """No FIND line appears verbatim, so the exhaustive tier seeds every start."""
    return "".join(_filler(FILE_LINES, "filler"))


def _scan_filter_recall(file_lines: List[str], find_lines: List[str]) -> Tuple[int, float]:
    """Highest true full ratio among the windows the sub-sample filter discards."""
    num_find_lines = len(find_lines)
    filtered = 0
    worst = 0.0
    for start in range(len(file_lines) - num_find_lines + 1):
        window = file_lines[start : start + num_find_lines]
        if _calculate_sub_sample_score(window, find_lines) >= SUB_SAMPLE_PASS_THRESHOLD:
            continue
        filtered += 1
        ratio = difflib.SequenceMatcher(None, window, find_lines).ratio()
        worst = max(worst, ratio)
    return filtered, worst


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
    return score, elapsed, is_ambiguous, decision


def _compare(label: str, content: str, find: str) -> None:
    cap_score, cap_s, cap_amb, cap_decision = _run(content, find, CANDIDATE_EVALUATION_CAP)
    full_score, full_s, full_amb, full_decision = _run(content, find, UNLIMITED)
    print(
        f"{label}: seeded={cap_decision.seeded} "
        f"cap(refined={cap_decision.refined} candidates={cap_decision.above_threshold} "
        f"ambiguous={cap_amb} ms={cap_s * 1000:.2f} score={cap_score:.4f}) | "
        f"full(refined={full_decision.refined} "
        f"candidates={full_decision.above_threshold} ambiguous={full_amb} "
        f"ms={full_s * 1000:.2f} score={full_score:.4f})"
    )


def main() -> None:
    install_recording_rule()
    find_lines = _large_find()
    find = "".join(find_lines)

    _compare(
        "two_large_near_duplicates",
        _near_duplicate_file(find_lines, copies=2),
        find,
    )

    disjoint = _disjoint_file()
    _compare("disjoint_exhaustive_pool", disjoint, find)

    filtered, worst = _scan_filter_recall(
        disjoint.splitlines(keepends=True), find_lines
    )
    print(
        f"filter_recall_scan: filtered={filtered} "
        f"worst_full_ratio_among_filtered={worst:.4f} "
        f"clears_threshold={worst >= THRESHOLD}"
    )


if __name__ == "__main__":
    main()
