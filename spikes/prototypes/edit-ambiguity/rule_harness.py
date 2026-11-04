"""Shared verdict harness for the slice 00-16 ambiguity-rule prototypes.

The production matcher flags a tie as ambiguous only when a candidate's raw
ratio equals the best ratio. The proposed rule additionally blocks a fuzzy
winner when the runner-up still clears the threshold. These helpers measure the
real candidate distribution and can install either an observational recorder or
the proposed rule into the production matcher, so the unmodified consumers
(EditSimulator and the EDIT validator) can be exercised end to end.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import List, Optional, Sequence

import teddy_executor.core.services.validation_rules.edit_matcher as edit_matcher
from teddy_executor.core.domain.models.plan import DEFAULT_SIMILARITY_THRESHOLD
from teddy_executor.core.services.validation_rules.edit_matcher import (
    LARGE_BLOCK_LINE_LIMIT,
    _apply_indentation_bonus,
    _apply_substring_boost,
)

_ORIGINAL_REFINE = edit_matcher._refine_and_select_best
_ORIGINAL_GATHER = edit_matcher.gather_candidate_starts
_LAST_DECISION: Optional["Decision"] = None
_SEEDED_WINDOWS = 0


@dataclass(frozen=True)
class Candidate:
    ratio: float
    match_lines: List[str]
    offset: int
    window_ambiguous: bool


@dataclass(frozen=True)
class Decision:
    top: float
    second: float
    ties: int
    above_threshold: int
    ambiguous: bool
    seeded: int = 0
    refined: int = 0


def decide(ratios: Sequence[float], threshold: float, seeded: int = 0) -> Decision:
    ordered = sorted(ratios, reverse=True)
    if not ordered:
        return Decision(-1.0, 0.0, 0, 0, False, seeded, 0)
    top = ordered[0]
    second = ordered[1] if len(ordered) > 1 else 0.0
    ties = sum(1 for ratio in ordered if ratio == top)
    above_threshold = sum(1 for ratio in ordered if ratio >= threshold)
    ambiguous = (ties > 1 and top >= threshold) or (top < 1.0 and second >= threshold)
    return Decision(
        top, second, ties, above_threshold, ambiguous, seeded, len(ordered)
    )


def last_decision() -> Decision:
    if _LAST_DECISION is None:
        raise RuntimeError("No matcher run has been recorded yet.")
    return _LAST_DECISION


def _measure(candidates, find_lines, num_find_lines, find_block) -> List[Candidate]:
    measured: List[Candidate] = []
    for score, window in candidates:
        if num_find_lines > LARGE_BLOCK_LINE_LIMIT:
            ratio = difflib.SequenceMatcher(None, window, find_lines).ratio()
        else:
            ratio = score
        ratio, offset = _apply_indentation_bonus(window, find_block, ratio)
        match_lines, ratio, window_ambiguous = _apply_substring_boost(
            window, find_lines, ratio
        )
        measured.append(Candidate(ratio, match_lines, offset, window_ambiguous))
    return measured


def _record(
    candidates, find_lines, num_find_lines, find_block, threshold
) -> tuple[List[Candidate], Decision]:
    global _LAST_DECISION
    measured = _measure(candidates, find_lines, num_find_lines, find_block)
    decision = decide(
        [candidate.ratio for candidate in measured], threshold, _SEEDED_WINDOWS
    )
    _LAST_DECISION = decision
    return measured, decision


def _install_observation() -> None:
    """Count the windows the heuristic tiers seed before the refinement cap."""

    def recording_gather(file_lines, find_lines, threshold):
        global _SEEDED_WINDOWS
        starts = _ORIGINAL_GATHER(file_lines, find_lines, threshold)
        _SEEDED_WINDOWS = len(starts)
        return starts

    edit_matcher.gather_candidate_starts = recording_gather


def install_recording_rule() -> None:
    """Observe the real distribution without changing matcher behaviour."""

    _install_observation()

    def recording_refine(
        candidates,
        find_lines,
        num_find_lines,
        find_block,
        threshold=DEFAULT_SIMILARITY_THRESHOLD,
    ):
        _record(candidates, find_lines, num_find_lines, find_block, threshold)
        return _ORIGINAL_REFINE(
            candidates, find_lines, num_find_lines, find_block, threshold
        )

    edit_matcher._refine_and_select_best = recording_refine


def install_refined_rule() -> None:
    """Install the proposed rule while keeping the production 4-tuple shape."""

    _install_observation()

    def refined_refine(
        candidates,
        find_lines,
        num_find_lines,
        find_block,
        threshold=DEFAULT_SIMILARITY_THRESHOLD,
    ):
        measured, decision = _record(
            candidates, find_lines, num_find_lines, find_block, threshold
        )
        if not measured:
            return _ORIGINAL_REFINE(
                candidates, find_lines, num_find_lines, find_block, threshold
            )
        best = measured[0]
        for candidate in measured[1:]:
            if candidate.ratio > best.ratio:
                best = candidate
        return (
            best.match_lines,
            best.ratio,
            decision.ambiguous or best.window_ambiguous,
            best.offset,
        )

    edit_matcher._refine_and_select_best = refined_refine
