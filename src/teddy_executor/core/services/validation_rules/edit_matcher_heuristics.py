"""
Tiered heuristic search for candidate window start positions in EditMatcher.
"""

import difflib
from collections import defaultdict
from typing import List, Set

SMALL_FILE_LINE_LIMIT = 100


def gather_candidate_starts(
    file_lines: List[str], find_lines: List[str], threshold: float
) -> Set[int]:
    """Orchestrates tiered heuristic search for candidate window start positions."""
    num_find_lines = len(find_lines)

    # Tier 1: Exact Priority Anchors
    candidate_starts = _find_starts_by_anchors(file_lines, find_lines)

    # Tier 2: Incremental Fuzzy Cascade (Fallback)
    if not candidate_starts:
        candidate_starts = _find_starts_by_fuzzy_cascade(
            file_lines, num_find_lines, find_lines[0], threshold
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
    file_lines: List[str],
    num_find_lines: int,
    first_find_line_raw: str,
    threshold: float,
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
        if matcher.real_quick_ratio() > threshold:
            if matcher.quick_ratio() > threshold:
                if 0 <= i <= len(file_lines) - num_find_lines:
                    candidate_starts.add(i)
    return candidate_starts
