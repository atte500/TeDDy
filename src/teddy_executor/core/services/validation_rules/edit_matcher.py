"""
Heuristic matching logic for the EDIT action validator.
"""

import difflib
import os
import time
from collections import defaultdict
from typing import List, Set

# Performance Heuristic Constants
FUZZY_RATIO_THRESHOLD = 0.8
SMALL_FILE_LINE_LIMIT = 100
LARGE_BLOCK_LINE_LIMIT = 20
SUB_SAMPLE_RATIO_THRESHOLD = 0.7
SUB_SAMPLE_PASS_THRESHOLD = 0.7
CANDIDATE_EVALUATION_CAP = 5


def find_best_match_and_diff(file_content: str, find_block: str) -> str:
    """
    Finds the most similar block of text in the file content and generates a diff.

    Performance Optimization:
    Uses a multi-layered heuristic to avoid quadratic complexity of difflib
    on large files (N lines) with large blocks (M lines).
    """
    debug = os.environ.get("TEDDY_DEBUG")
    start_total = time.perf_counter()

    file_lines = file_content.splitlines(keepends=True)
    find_lines = find_block.splitlines(keepends=True)
    num_find_lines = len(find_lines)

    if not file_lines or not find_lines:
        return ""

    # If the file is smaller than the find block, just compare against the whole file
    if len(file_lines) < num_find_lines:
        diff = difflib.ndiff(find_lines, file_lines)
        return "\n".join(line.rstrip("\n\r") for line in diff)

    # 1. Gather Candidates using Tiered Heuristics
    start_gather = time.perf_counter()
    candidate_starts = _gather_candidate_starts(file_lines, find_lines)
    gather_duration = time.perf_counter() - start_gather

    # 2. Evaluate Candidates with sub-sampling optimization
    start_eval = time.perf_counter()
    best_match_lines = _evaluate_candidates(
        file_lines, find_lines, candidate_starts, find_block
    )
    eval_duration = time.perf_counter() - start_eval

    if best_match_lines:
        start_diff = time.perf_counter()
        diff = difflib.ndiff(find_lines, best_match_lines)
        res = "\n".join(line.rstrip("\n\r") for line in diff)
        diff_duration = time.perf_counter() - start_diff

        if debug:
            print("--- MATCHER PROFILING ---")
            print(f"Candidates: {len(candidate_starts)}")
            print(f"Gather: {gather_duration:.4f}s")
            print(f"Eval:   {eval_duration:.4f}s")
            print(f"Diff:   {diff_duration:.4f}s")
            print(f"Total:  {time.perf_counter() - start_total:.4f}s")
            print("-------------------------")
        return res

    return ""


def _get_quick_ratio(line1: str, line2: str) -> float:
    """
    Calculates a fast fuzzy similarity ratio between two strings.
    Used for pre-filtering candidate windows.
    """
    return difflib.SequenceMatcher(None, line1, line2).quick_ratio()


def _gather_candidate_starts(file_lines: List[str], find_lines: List[str]) -> Set[int]:
    """Orchestrates tiered heuristic search for candidate window start positions."""
    num_find_lines = len(find_lines)

    # Tier 1: Exact Priority Anchors
    candidate_starts = _find_starts_by_anchors(file_lines, find_lines)

    # Tier 2: Incremental Fuzzy Cascade (Fallback)
    if not candidate_starts:
        candidate_starts = _find_starts_by_fuzzy_cascade(
            file_lines, num_find_lines, find_lines[0]
        )

    # Tier 3: Exhaustive Fallback for Small Files
    if not candidate_starts and len(file_lines) < SMALL_FILE_LINE_LIMIT:
        candidate_starts = set(range(len(file_lines) - num_find_lines + 1))

    return candidate_starts


def _find_starts_by_anchors(file_lines: List[str], find_lines: List[str]) -> Set[int]:
    """Tier 1: Find candidate windows by matching the longest unique 'anchor' lines."""
    num_find_lines = len(find_lines)
    priority_lines = sorted(
        [(line.strip(), i) for i, line in enumerate(find_lines) if line.strip()],
        key=lambda x: len(x[0]),
        reverse=True,
    )[:5]

    file_line_map = defaultdict(list)
    for i, line in enumerate(file_lines):
        trimmed = line.strip()
        if trimmed:
            file_line_map[trimmed].append(i)

    candidate_starts: Set[int] = set()
    for trimmed, find_idx in priority_lines:
        if trimmed in file_line_map:
            for file_idx in file_line_map[trimmed]:
                start = file_idx - find_idx
                if 0 <= start <= len(file_lines) - num_find_lines:
                    candidate_starts.add(start)
    return candidate_starts


def _find_starts_by_fuzzy_cascade(
    file_lines: List[str], num_find_lines: int, first_find_line_raw: str
) -> Set[int]:
    """Tier 2: Find candidate windows by fuzzy matching the first line of the block."""
    candidate_starts: Set[int] = set()
    first_find_line = first_find_line_raw.strip()
    for i, f_line in enumerate(file_lines):
        if _get_quick_ratio(f_line.strip(), first_find_line) > FUZZY_RATIO_THRESHOLD:
            if 0 <= i <= len(file_lines) - num_find_lines:
                candidate_starts.add(i)
    return candidate_starts


def _evaluate_candidates(
    file_lines: List[str],
    find_lines: List[str],
    candidate_starts: Set[int],
    find_block: str,
) -> List[str]:
    """Evaluates candidates using difflib ratio, with sub-sampling and priority capping."""
    best_ratio = -1.0
    best_match_lines: List[str] = []
    num_find_lines = len(find_lines)

    debug = os.environ.get("TEDDY_DEBUG")
    scored_candidates = []

    for start in candidate_starts:
        window = file_lines[start : start + num_find_lines]

        if num_find_lines > LARGE_BLOCK_LINE_LIMIT:
            score = _calculate_sub_sample_score(window, find_lines)
            if score >= SUB_SAMPLE_PASS_THRESHOLD:
                scored_candidates.append((score, window))
        else:
            # For small blocks, the ratio calculation is fast enough
            matcher = difflib.SequenceMatcher(None, "".join(window), find_block)
            scored_candidates.append((matcher.ratio(), window))

    # Sort by score descending and cap evaluation
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    candidates_to_refine = scored_candidates[:CANDIDATE_EVALUATION_CAP]

    # FALLBACK: If no candidates were found via heuristics, but the file is not empty,
    # pick the very first block of the same size to at least provide a baseline diff.
    if not candidates_to_refine and file_lines:
        candidates_to_refine = [(0.0, file_lines[:num_find_lines])]

    ratio_calls = 0
    for score, window in candidates_to_refine:
        if num_find_lines > LARGE_BLOCK_LINE_LIMIT:
            # Perform expensive character-based refinement for large blocks
            matcher = difflib.SequenceMatcher(None, window, find_lines)
            ratio = matcher.ratio()
        else:
            # Score already calculated for small blocks
            ratio = score

        ratio_calls += 1
        if ratio > best_ratio:
            best_ratio = ratio
            best_match_lines = window
    if debug:
        print(f"Candidates Scored: {len(candidate_starts)}")
        print(f"Top Candidates Refined: {len(candidates_to_refine)}")
        print(f"Ratio Calls: {ratio_calls}")

    return best_match_lines


def _calculate_sub_sample_score(window: List[str], find_lines: List[str]) -> float:
    """Calculates a quick sub-sampled similarity score for large blocks."""
    num_find_lines = len(find_lines)
    sub_sample_matches = 0
    total_checks = 0
    # Check up to 10 representative lines distributed across the block.
    step = max(1, num_find_lines // 10)
    for k in range(0, num_find_lines, step):
        total_checks += 1
        if (
            _get_quick_ratio(window[k].strip(), find_lines[k].strip())
            > SUB_SAMPLE_RATIO_THRESHOLD
        ):
            sub_sample_matches += 1

    return sub_sample_matches / total_checks
