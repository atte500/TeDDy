# Bug: EditMatcher cannot anchor multi-line FIND blocks on partial fragments of long single lines

- **Status:** Unresolved
- **Milestone:** [docs/project/milestones/05-quality-gate-debt-reconciliation.md](/docs/project/milestones/05-quality-gate-debt-reconciliation.md)
- **Vertical Slice:** N/A
- **Specs:** N/A

## Symptoms

**Expected behavior:**
A multi-line FIND block whose lines are partial fragments of long single lines (e.g., a Case File Investigation History entry, which is a single ~1500-character line) matches the containing line(s) and applies the edit, reporting a high Similarity Score.

**Actual behavior:**
The matcher rejects the edit with a low Similarity Score (observed: 0.12 against the 0.95 threshold), even though the fragment text appears verbatim inside the file. Observed live during Case File 49 (turns 21/23/25 EDIT validation failures on the same Case File).

**Minimal reproduction steps:**
1. Target a file containing a very long single line (e.g., a Case File Investigation History entry).
2. Submit an EDIT whose FIND block is multi-line, with its first line being a mid-line fragment of that long line (e.g., the tail ~90 characters of the ~1500-character entry).
3. Validation fails with `Similarity Score: 0.12` despite the fragment being an exact substring of the file.

## Context & Scope

### Regressing Delta

Not a regression — a design limitation of the EditMatcher, discovered during the Case File 49 harness meta-audit (CF49 turn 27, user-requested). `find_best_match()` in `edit_matcher.py` is line-window based: the FIND block is split into lines and candidate windows of equal line count are scored via `difflib.SequenceMatcher` over the joined text. The only sub-line support, `_apply_substring_boost()`, fires ONLY when the FIND block is a single line; the Tier 3 candidate enumeration in `edit_matcher_heuristics.py` likewise only handles `num_find_lines == 1`.

### Environmental Triggers

- Multi-line FIND block (>= 2 lines) where at least one line is a partial fragment of a long single-line file entry.
- Any target file with very long single lines — TeDDy Case Files (Investigation History entries) produce exactly this shape routinely, making agent-driven Case File edits prone to this failure.

### Ruled Out

- **TeDDy EDIT pipeline correctness bug:** the CF49 turn-27 audit proved the validator (`validation_rules/edit.py`) and the executor (`edit_simulator.py`) both delegate to the same `find_best_match()`; validation and execution cannot diverge, and the reported 0.12 score is the genuine, mathematically correct score for that input (approximately 2·M/(len(window)+len(find)) for a ~100-char fragment against a ~1500-char line window).
- **CRLF / line-ending normalization:** ruled out — anchors strip whitespace, the substring boost rstrips `\r\n`, and CRLF only marginally affects multi-line ratio computation.

## Diagnostic Analysis

### Causal Model

For a multi-line FIND block, candidate windows are scored by joining the window lines and the FIND lines and running `difflib.SequenceMatcher.ratio()`. When a FIND line is a short fragment of a very long file line, the joined-window text is dominated by the unrelated remainder of that line, so the ratio degenerates to approximately fragment_length / line_length (observed 0.12). The substring boost that would rescue this case (score 1.0 for an exact intra-line substring match) is gated on `len(find_lines) == 1`, so multi-line FIND blocks never receive it; Tier 3 anchor enumeration correspondingly never considers intra-line positions for multi-line FIND blocks. Net effect: partial-line anchoring works only for single-line FINDs.

### Discrepancies

- None open — the mechanism was fully source-confirmed during the CF49 turn-27 audit (all four pipeline components read; repo-wide similarity census completed).

### Investigation History

1. **Hypothesis:** the repeated Case File 49 EDIT validation failures (turns 21/23/25) could be a bug in TeDDy's own EDIT pipeline, since the session runs inside TeDDy itself. **Observation:** full source read of `validation_rules/edit.py`, `edit_matcher.py`, `edit_matcher_heuristics.py`, `edit_simulator.py`, plus a repo-wide `git grep` census of similarity computation/reporting sites. **Conclusion:** NOT a correctness bug — one matcher serves both validation and execution; the 0.12 score is the correct score for a partial-line multi-line FIND against a ~1500-char single-line entry. The genuine finding is the single-line-only substring boost (design gap), formalized as this Case File.

## Solution

TBD.
