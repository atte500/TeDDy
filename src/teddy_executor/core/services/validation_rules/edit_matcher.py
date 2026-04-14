"""
Heuristic matching logic for the EDIT action validator.
"""

import difflib
import os
import time
from typing import List, Set

from teddy_executor.core.domain.models.plan import DEFAULT_SIMILARITY_THRESHOLD
from teddy_executor.core.services.validation_rules.edit_matcher_heuristics import (
    gather_candidate_starts,
)

# Performance Heuristic Constants
LARGE_BLOCK_LINE_LIMIT = 20
SUB_SAMPLE_RATIO_THRESHOLD = 0.7
SUB_SAMPLE_PASS_THRESHOLD = 0.7
CANDIDATE_EVALUATION_CAP = 5


def find_best_match(
    file_content: str,
    find_block: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> tuple[str, float, bool, int]:
    """
    Finds the most similar block of text in the file content.

    Returns:
        tuple[str, float, bool, int]: (best_match_string, best_score, is_ambiguous, offset)
    """
    file_lines = file_content.splitlines(keepends=True)
    find_lines = find_block.splitlines(keepends=True)
    num_find_lines = len(find_lines)

    if not file_lines or not find_lines:
        return "", 0.0, False, 0

    # If the file is smaller than the find block, just compare against the whole file
    if len(file_lines) < num_find_lines:
        matcher = difflib.SequenceMatcher(None, find_lines, file_lines)
        score = matcher.ratio()
        return "".join(file_lines), round(score, 2), False, 0

    candidate_starts = gather_candidate_starts(file_lines, find_lines, threshold)
    best_match_lines, score, is_ambiguous, offset = _evaluate_candidates(
        file_lines, find_lines, candidate_starts, find_block
    )

    return "".join(best_match_lines), round(score, 2), is_ambiguous, offset


def find_best_match_and_diff(
    file_content: str,
    find_block: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> tuple[str, float, bool, int]:
    """
    Finds the most similar block of text in the file content and generates a diff.
    Uses character-level ndiff (with ? markers) for fuzzy matches.

    Returns:
        tuple[str, float, bool, int]: (diff_text, best_score, is_ambiguous, offset)
    """
    debug = os.environ.get("TEDDY_DEBUG")
    start_total = time.perf_counter()

    best_match_str, score, is_ambiguous, offset = find_best_match(
        file_content, find_block, threshold
    )

    res = ""
    if best_match_str and not is_ambiguous:
        # Generate character-level diff only for non-perfect matches
        # Note: score is already rounded to 2 decimal places by find_best_match
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

    return res, score, is_ambiguous, offset


def _evaluate_candidates(
    file_lines: List[str],
    find_lines: List[str],
    candidate_starts: Set[int],
    find_block: str,
) -> tuple[List[str], float, bool, int]:
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
            window_str = "".join(window)
            matcher = difflib.SequenceMatcher(None, window_str, find_block)
            score = matcher.ratio()
            scored_candidates.append((score, window))

    # Sort by score descending and cap evaluation
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    candidates_to_refine = scored_candidates[:CANDIDATE_EVALUATION_CAP]

    # FALLBACK: pick first block if no candidates found
    if not candidates_to_refine and file_lines:
        candidates_to_refine = [(0.0, file_lines[:num_find_lines])]

    return _refine_and_select_best(
        candidates_to_refine, find_lines, num_find_lines, find_block
    )


def _refine_and_select_best(
    candidates: List[tuple[float, List[str]]],
    find_lines: List[str],
    num_find_lines: int,
    find_block: str,
) -> tuple[List[str], float, bool, int]:
    """Refines top candidates and returns the best match with ambiguity info."""
    best_ratio = -1.0
    best_match_lines: List[str] = []
    is_ambiguous = False
    best_offset = 0
    ratio_calls = 0

    for score, window in candidates:
        if num_find_lines > LARGE_BLOCK_LINE_LIMIT:
            matcher = difflib.SequenceMatcher(None, window, find_lines)
            ratio = matcher.ratio()
        else:
            ratio = score

        # Whitespace Indifference Bonus & Indentation Offset
        ratio, current_offset = _apply_indentation_bonus(window, find_block, ratio)

        current_match_lines, ratio, current_is_ambiguous = _apply_substring_boost(
            window, find_lines, ratio
        )

        ratio_calls += 1
        if ratio > best_ratio:
            best_ratio = ratio
            best_match_lines = current_match_lines
            is_ambiguous = current_is_ambiguous
            best_offset = current_offset
        elif ratio == best_ratio and ratio > 0:
            is_ambiguous = True

    if os.environ.get("TEDDY_DEBUG"):
        print(f"Top Candidates Refined: {len(candidates)}")
        print(f"Ratio Calls: {ratio_calls}")

    return best_match_lines, best_ratio, is_ambiguous, best_offset


def _apply_indentation_bonus(
    window: List[str], find_block: str, current_ratio: float
) -> tuple[float, int]:
    """
    Applies 1.0 score boost if window matches find_block logic exactly,
    ignoring trailing whitespace and constant relative indentation.
    """
    ratio = current_ratio
    offset = 0
    if ratio >= 1.0:
        return ratio, offset

    w_lines = [line.rstrip() for line in window]
    f_lines = [line.rstrip() for line in find_block.splitlines(keepends=True)]

    if len(w_lines) != len(f_lines):
        return ratio, offset

    offsets = []
    for w_line, f_line in zip(w_lines, f_lines):
        w_stripped = w_line.lstrip()
        f_stripped = f_line.lstrip()
        if w_stripped != f_stripped:
            return ratio, offset
        if w_stripped:  # Only calculate offset for non-empty lines
            offsets.append(
                len(w_line) - len(w_stripped) - (len(f_line) - len(f_stripped))
            )

    if offsets and len(set(offsets)) == 1:
        ratio = 1.0
        offset = offsets[0]

    return ratio, offset


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
