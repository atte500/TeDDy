"""
Heuristic matching logic for the EDIT action validator.
"""

import difflib
import os
import time
from collections import defaultdict
from typing import List, Set

# Performance Heuristic Constants
FUZZY_RATIO_THRESHOLD = 0.95
SMALL_FILE_LINE_LIMIT = 100
LARGE_BLOCK_LINE_LIMIT = 20
SUB_SAMPLE_RATIO_THRESHOLD = 0.7
SUB_SAMPLE_PASS_THRESHOLD = 0.7
CANDIDATE_EVALUATION_CAP = 5


def find_best_match(
    file_content: str, find_block: str, threshold: float = FUZZY_RATIO_THRESHOLD
) -> tuple[str, float, bool]:
    """
    Finds the most similar block of text in the file content.

    Returns:
        tuple[str, float, bool]: (best_match_string, best_score, is_ambiguous)
    """
    file_lines = file_content.splitlines(keepends=True)
    find_lines = find_block.splitlines(keepends=True)
    num_find_lines = len(find_lines)

    if not file_lines or not find_lines:
        return "", 0.0, False

    # If the file is smaller than the find block, just compare against the whole file
    if len(file_lines) < num_find_lines:
        matcher = difflib.SequenceMatcher(None, find_lines, file_lines)
        score = matcher.ratio()
        return "".join(file_lines), score, False

    candidate_starts = _gather_candidate_starts(file_lines, find_lines)
    best_match_lines, score, is_ambiguous = _evaluate_candidates(
        file_lines, find_lines, candidate_starts, find_block
    )

    return "".join(best_match_lines), score, is_ambiguous


def find_best_match_and_diff(
    file_content: str, find_block: str, threshold: float = FUZZY_RATIO_THRESHOLD
) -> tuple[str, float, bool]:
    """
    Finds the most similar block of text in the file content and generates a diff.
    Uses character-level ndiff (with ? markers) for fuzzy matches.

    Returns:
        tuple[str, float, bool]: (diff_text, best_score, is_ambiguous)
    """
    debug = os.environ.get("TEDDY_DEBUG")
    start_total = time.perf_counter()

    best_match_str, score, is_ambiguous = find_best_match(
        file_content, find_block, threshold
    )

    res = ""
    if best_match_str and not is_ambiguous:
        # Generate character-level diff only for non-perfect matches
        if 0 < score < 1.0:
            find_lines = find_block.splitlines(keepends=True)
            match_lines = best_match_str.splitlines(keepends=True)
            # ndiff provides the '?' lines for intra-line changes
            diff = difflib.ndiff(find_lines, match_lines)
            res = "\n".join(line.rstrip("\n\r") for line in diff)

        if debug:
            print("--- MATCHER PROFILING ---")
            print(f"Total:  {time.perf_counter() - start_total:.4f}s")
            print("-------------------------")

    return res, score, is_ambiguous


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

    # Tier 3: Substring Fallback (For single-word or intra-line matches)
    if not candidate_starts and num_find_lines == 1:
        find_text = find_lines[0].strip()
        for i, line in enumerate(file_lines):
            if find_text in line:
                candidate_starts.add(i)

    # Tier 4: Exhaustive Fallback for Small Files
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
    """
    Tier 2: Find candidate windows by fuzzy matching the first line of the block.
    Uses real_quick_ratio as a fast pre-filter before checking quick_ratio.
    """
    candidate_starts: Set[int] = set()
    first_find_line = first_find_line_raw.strip()
    for i, f_line in enumerate(file_lines):
        f_line_stripped = f_line.strip()
        # Pre-filter with real_quick_ratio which is O(N+M) and very fast
        matcher = difflib.SequenceMatcher(None, f_line_stripped, first_find_line)
        if matcher.real_quick_ratio() > FUZZY_RATIO_THRESHOLD:
            if matcher.quick_ratio() > FUZZY_RATIO_THRESHOLD:
                if 0 <= i <= len(file_lines) - num_find_lines:
                    candidate_starts.add(i)
    return candidate_starts


def _evaluate_candidates(
    file_lines: List[str],
    find_lines: List[str],
    candidate_starts: Set[int],
    find_block: str,
) -> tuple[List[str], float, bool]:
    """Evaluates candidates using difflib ratio, with sub-sampling and priority capping."""
    num_find_lines = len(find_lines)
    scored_candidates = []

    for start in candidate_starts:
        window = file_lines[start : start + num_find_lines]
        if num_find_lines > LARGE_BLOCK_LINE_LIMIT:
            score = _calculate_sub_sample_score(window, find_lines)
            if score >= SUB_SAMPLE_PASS_THRESHOLD:
                scored_candidates.append((score, window))
        else:
            matcher = difflib.SequenceMatcher(None, "".join(window), find_block)
            scored_candidates.append((matcher.ratio(), window))

    # Sort by score descending and cap evaluation
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    candidates_to_refine = scored_candidates[:CANDIDATE_EVALUATION_CAP]

    # FALLBACK: pick first block if no candidates found
    if not candidates_to_refine and file_lines:
        candidates_to_refine = [(0.0, file_lines[:num_find_lines])]

    return _refine_and_select_best(candidates_to_refine, find_lines, num_find_lines)


def _refine_and_select_best(
    candidates: List[tuple[float, List[str]]],
    find_lines: List[str],
    num_find_lines: int,
) -> tuple[List[str], float, bool]:
    """Refines top candidates and returns the best match with ambiguity info."""
    best_ratio = -1.0
    best_match_lines: List[str] = []
    is_ambiguous = False
    ratio_calls = 0

    for score, window in candidates:
        if num_find_lines > LARGE_BLOCK_LINE_LIMIT:
            matcher = difflib.SequenceMatcher(None, window, find_lines)
            ratio = matcher.ratio()
        else:
            ratio = score

        current_match_lines, ratio, current_is_ambiguous = _apply_substring_boost(
            window, find_lines, ratio
        )

        ratio_calls += 1
        if ratio > best_ratio:
            best_ratio = ratio
            best_match_lines = current_match_lines
            is_ambiguous = current_is_ambiguous
        elif ratio == best_ratio and ratio > 0:
            is_ambiguous = True

    if os.environ.get("TEDDY_DEBUG"):
        print(f"Top Candidates Refined: {len(candidates)}")
        print(f"Ratio Calls: {ratio_calls}")

    return best_match_lines, best_ratio, is_ambiguous


def _apply_substring_boost(
    window: List[str], find_lines: List[str], current_ratio: float
) -> tuple[List[str], float, bool]:
    """
    Applies Substring Boost: If a single-line block matches a substring exactly,
    ratio is 1.0. This handles surgical intra-line replacements.
    """
    ratio = current_ratio
    match_lines = window
    is_ambiguous = False

    if ratio < 1.0 and len(find_lines) == 1:
        find_text = find_lines[0].rstrip("\n\r")
        if find_text and find_text in window[0]:
            match_count = window[0].count(find_text)
            ratio = 1.0
            match_lines = [find_text]
            if match_count > 1:
                # Intra-line ambiguity detected
                is_ambiguous = True

    return match_lines, ratio, is_ambiguous


def _calculate_sub_sample_score(window: List[str], find_lines: List[str]) -> float:
    """
    Calculates a lightning-fast similarity score for large blocks.
    Uses simple string equality on a sub-sample of lines to avoid the
    overhead of difflib.SequenceMatcher.quick_ratio() during the filter phase.
    """
    num_find_lines = len(find_lines)
    sub_sample_matches = 0
    total_checks = 0
    # Check up to 10 representative lines distributed across the block.
    step = max(1, num_find_lines // 10)
    for k in range(0, num_find_lines, step):
        total_checks += 1
        # Simple equality is O(N) where N is line length, much faster than quick_ratio
        if window[k].strip() == find_lines[k].strip():
            sub_sample_matches += 1

    return sub_sample_matches / total_checks
