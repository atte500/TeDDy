"""
Heuristic matching logic for the EDIT action validator.
"""

import difflib
from collections import defaultdict
from typing import List, Set

# Performance Heuristic Constants
FUZZY_RATIO_THRESHOLD = 0.8
SMALL_FILE_LINE_LIMIT = 100
LARGE_BLOCK_LINE_LIMIT = 20
SUB_SAMPLE_RATIO_THRESHOLD = 0.7
SUB_SAMPLE_PASS_THRESHOLD = 0.4


def find_best_match_and_diff(file_content: str, find_block: str) -> str:
    """
    Finds the most similar block of text in the file content and generates a diff.

    Performance Optimization:
    Uses a multi-layered heuristic to avoid quadratic complexity of difflib
    on large files (N lines) with large blocks (M lines).
    """
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
    candidate_starts = _gather_candidate_starts(file_lines, find_lines)

    # 2. Evaluate Candidates with sub-sampling optimization
    best_match_lines = _evaluate_candidates(
        file_lines, find_lines, candidate_starts, find_block
    )

    if best_match_lines:
        diff = difflib.ndiff(find_lines, best_match_lines)
        return "\n".join(line.rstrip("\n\r") for line in diff)

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
    """Evaluates candidates using difflib ratio, with sub-sampling for large blocks."""
    best_ratio = -1.0
    best_match_lines: List[str] = []
    num_find_lines = len(find_lines)

    for start in candidate_starts:
        window = file_lines[start : start + num_find_lines]

        # Hybrid Matching Strategy:
        # 1. Large Blocks: Use line-based matching for O(N) performance.
        # 2. Small Blocks: Use character-based matching for precision (e.g. typos).
        if num_find_lines > LARGE_BLOCK_LINE_LIMIT:
            if not _is_promising_candidate(window, find_lines):
                continue
            matcher = difflib.SequenceMatcher(None, window, find_lines)
        else:
            matcher = difflib.SequenceMatcher(None, "".join(window), find_block)

        ratio = matcher.ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match_lines = window
    return best_match_lines


def _is_promising_candidate(window: List[str], find_lines: List[str]) -> bool:
    """Performs a quick sub-sampled ratio check for large blocks."""
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

    return (sub_sample_matches / total_checks) >= SUB_SAMPLE_PASS_THRESHOLD
