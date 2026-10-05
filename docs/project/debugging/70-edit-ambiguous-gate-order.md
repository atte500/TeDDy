# Bug: EDIT Ambiguous Check Fires Before Threshold Check
- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms
When `_validate_single_edit` receives `is_ambiguous=True` with a similarity score well below the threshold (e.g., 0.10), it emits "The FIND block is ambiguous" instead of "The FIND block could not be located" with a helpful Closest Match Diff. The agent receives no guidance on why the match failed and cannot recover.

**Expected:** "The FIND block could not be located" with similarity score, closest match diff, and remediation hint.
**Actual:** "The FIND block is ambiguous" with similarity score, no diff guidance, and no actionable recovery path.

**Minimal Reproduction:**
- Any FIND block whose best tied candidate scores below the effective threshold but was still flagged `is_ambiguous=True` by the (then un-gated) matcher (observed at 0.10 under the 0.95 default).
- Common with short, generic FIND blocks that partially match many file windows, causing candidates to tie at low scores.

## Context & Scope
### Regressing Delta
N/A — This is a logic bug present since the introduction of the ambiguous-check heuristic, not a regression from a specific commit.

### Environmental Triggers
- Default or user-configured `similarity_threshold` (from config.yaml / action params) above the matcher's returned score.
- A FIND block that produces tied candidates at low similarity scores (e.g., 0.10).
- `match_all` not set to `true`.

### Ruled Out
- The `gather_candidate_starts` heuristic tiers (Tier 1–4) are working as designed — the exhaustive fallback (Tier 4) is intentionally triggered when no strong candidates exist.
- The `_apply_substring_boost` and `_apply_indentation_bonus` modifiers are correct logic; they only fire when a genuine match exists.
- No other code path in the validation pipeline systematically produces false positives.

## Diagnostic Analysis
### Causal Model
Two distinct bugs compound to produce the symptom:

**Bug A (Primary — edit.py `_validate_single_edit`):**
The condition check order is:
1. `if is_ambiguous and not match_all:` → returns ambiguous error (no diff)
2. `elif score < effective_threshold:` → returns "not found" with diff (never reached if #1 fires)

Because the ambiguous check has no score gate, any `is_ambiguous=True` — even at score 0.10 — triggers the ambiguous error. The "not found" branch, which includes the Closest Match Diff and actionable hints, is skipped entirely.

**Bug B (Compounding — edit_matcher.py `_refine_and_select_best`):**
`is_ambiguous` is set to `True` when `ratio == best_ratio and ratio > 0` — i.e., any tie at any positive ratio, regardless of how low. For a short FIND block that doesn't match well, many file windows can tie at the same low ratio (e.g., 0.10), causing the ambiguous flag. This is overly aggressive: ties at low scores are "equally bad" not "genuinely ambiguous".

**Crucial subtlety (discovered during verification):** the ambiguity gate MUST be relative to the *effective* threshold the caller passed (which may be a custom `execution.similarity_threshold` below the default, e.g. 0.80), NOT the module-level `DEFAULT_SIMILARITY_THRESHOLD` constant (0.95). The matcher already receives `threshold` in `find_best_match`; it simply was never threaded down into the ambiguity decision. Gating on the module constant (an interim, incorrect attempt) silently drops a genuine tie at a custom threshold: a tie at 0.80 under a 0.80 threshold is no longer flagged, letting the validator accept the first of several equal candidates — a correctness regression.

### Discrepancies
- The ambiguous check in `edit.py` must require `score >= effective_threshold` before firing. (Resolved: `and score >= effective_threshold` added to the ambiguous branch.)
- `_refine_and_select_best` in `edit_matcher.py` must gate `is_ambiguous` on the *effective* threshold. (Resolved: `threshold` threaded through `_evaluate_candidates` → `_refine_and_select_best`; tie gated on `ratio >= threshold`.)
- Gating on the module-level `DEFAULT_SIMILARITY_THRESHOLD` constant is INCORRECT — it breaks custom thresholds below the default. (Resolved: superseded by the effective-threshold threading; verified by the real-MRE S1b scenario at threshold 0.80.)

### Investigation History
1. Static reading of `edit.py` confirmed the condition-order bug: the ambiguous branch was evaluated before the threshold branch.
2. Static reading of `edit_matcher.py` confirmed the un-gated `is_ambiguous = True` at `ratio == best_ratio and ratio > 0`.
3. An inline-simulation MRE confirmed the *shape* of the bug (Bug A returns "ambiguous_error" at score 0.10 instead of "not_found_with_diff"; Bug B returns `is_ambiguous=True` for a 0.10 tie). This simulation does NOT exercise production source and is therefore NOT valid verification evidence; it was superseded by the real MRE (entry 6).
4. (RETRACTED) An earlier revision claimed "shadow-file verification confirmed the one-line fixes". This is FALSE: the Turn-12 plan that would have created the shadow files ABORTED when a bare `python` invocation failed (exit 127); both shadow `CREATE` actions were SKIPPED, so no shadow verification ever occurred.
5. An interim fix shipped: the matcher tie gated on the module-level `DEFAULT_SIMILARITY_THRESHOLD` (0.95) in `edit_matcher.py`, plus the `score >= effective_threshold` gate in `edit.py`.
6. A real, live-source MRE (`spikes/debug/70-edit-ambiguous-real-mre.py`, importing the actual `find_best_match_and_diff` and `_validate_single_edit`) exposed that the interim matcher fix was WRONG: for a custom threshold of 0.80, a genuine tie at 0.80 was NOT flagged ambiguous (matcher `is_ambiguous=False`), so the validator accepted the first candidate — a correctness regression.
7. Corrected fix: threaded the effective `threshold` from `find_best_match` → `_evaluate_candidates` → `_refine_and_select_best` and gated the tie on `ratio >= threshold`. The real MRE then reported ALL PASS: low-score tie @0.95 → "not_found"; tie @0.80 → "ambiguous"; genuine ambiguity @0.95 → "ambiguous".
8. Regression test `tests/suites/unit/core/services/test_edit_ambiguity_threshold_gating.py` (4 tests) added. RED via `git stash` (2 failed: sub-threshold tie mis-labelled ambiguous); GREEN after `git stash pop` (4 passed). Full suite: 1622 passed, 5 skipped.

## Solution
### Root Cause
The `if is_ambiguous and not match_all:` check in `edit.py` lacked a `score >= effective_threshold` guard, and the matcher's `is_ambiguous` was set for ties at ANY positive score (`ratio > 0`). Because the ambiguous branch was evaluated before the threshold branch — and the matcher never compared the tie against the caller's effective threshold — the agent received a misleading "ambiguous" error with no diff guidance for FIND blocks that merely failed to match.

### Fix (applied to source)
1. **edit.py (`_validate_single_edit`):** the ambiguous condition now reads `if is_ambiguous and not match_all and score >= effective_threshold:` — the ambiguous error only fires when the match score is meaningful (at/above the effective threshold) but ambiguous.

2. **edit_matcher.py (`find_best_match` / `_evaluate_candidates` / `_refine_and_select_best`):** the effective `threshold` is threaded into candidate evaluation (`_evaluate_candidates(..., threshold)`) and down to `_refine_and_select_best(..., threshold)`, whose tie condition now reads `elif ratio == best_ratio and ratio > 0 and ratio >= threshold:`. A tie is flagged ambiguous only when it meets the *caller's effective* threshold — never the module constant.

### Preventative Measures
- Ambiguity detection MUST be gated on the **effective** similarity threshold (the value actually used for this edit), resolved as action-params → global config → domain default. Gating on a module-level constant (`DEFAULT_SIMILARITY_THRESHOLD`) is a defect: it breaks any custom threshold below the default.
- Every decision point in the edit-matching pipeline that compares a score against "how good is good enough" MUST consume the same `threshold` value threaded from the caller, so routing and gating cannot diverge.
- The `EditSimulator` (`edit_simulator.py`) repeats the same ambiguous-consumer shape but calls the same matcher, so it is fixed centrally by this matcher change (no separate edit needed).
