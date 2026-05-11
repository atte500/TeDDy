# Bug: Auto-Pruning Ineffective in Interactive Sessions

- **Status:** Resolved
- **Milestone:** [10-interactive-session-and-config](../milestones/10-interactive-session-and-config.md)
- **Vertical Slice:** [00-04-context-management-ui](../slices/00-04-context-management-ui.md)
- **Specs:** [context-management-ui](../specs/context-management-ui.md)

## Symptoms
Expected: In an interactive session, if auto-pruning is enabled, files matching certain criteria (like failed reports or large token counts) should be pre-deselected in the TUI (showing as dimmed/strikethrough).
Actual: All files appear selected by default regardless of their status or size.

## Context & Scope
### Regressing Delta
The implementation of `_apply_auto_pruning` in `SessionOrchestrator` and its integration in the `execute` method (Slice 00-04).

### Environmental Triggers
Interactive session mode (`teddy resume` or `teddy start`).

### Ruled Out
TUI rendering logic for pruned items (verified in `00-04` prototype and acceptance tests).

## Diagnostic Analysis
### Causal Model
1. `SessionOrchestrator.execute` is called.
2. It calls `context_service.get_context()` to gather all relevant files.
3. It calls `_pruning_service.prune(project_context)` to modify the `selected` and `auto_prune_reason` fields of `ContextItem`s.
4. `SessionPruningService.prune` uses `re.search(r"(?:^|/)(\d+)/", item.path)` to extract turn IDs.
5. For failures in Turn N, it calculates the target turn N-1 using `f"{int(turn_id) - 1:02d}"`.
6. If the turn directory is not zero-padded (e.g., `1`), the extracted ID `"1"` fails to match the target `"01"`.
7. Pruning is bypassed, and the enriched `ProjectContext` is passed to the TUI with `selected=True`.
8. The TUI renders the items normally, making auto-pruning appear ineffective.

### Discrepancies
- Pruning Logic Regex. The regex `r"(?:^|/)(\d+)/"` is greedy and matches parent directories or session names if they contain numbers. (Resolved: Updated regex to `r"(?:^|/)(\d{1,3})(?=/|$)"` to target turn IDs precisely.)
- Padding Mismatch. The use of `:02d` padding for target IDs mismatches unpadded directory extracts. (Resolved: Implemented dual matching strategy (string + integer) to normalize comparisons.)
- Validation Check. "Status: Validation Failed" was too strict. (Resolved: Updated to substring match for "Validation Failed".)
- Windows Path Separators. The regex `r"(?:^|/)(\d{1,3})(?=/|$)"` only accounts for forward slashes, causing extraction failure on Windows.

### Investigation History
1. Initial report. User observes auto-pruning is not taking effect in real sessions.
2. Diagnostic Probe. Confirmed that `SessionOrchestrator.execute` is reached but pruning logic is bypassed for certain paths.
3. Padding Spike. Verified that hardcoded `:02d` padding causes comparison failures for single-digit turns.
4. TUI Logic Audit. Verified that TUI correctly renders the `selected` state if the domain model sets it correctly.
5. Acceptance Verification. Refined test stubbing and resolved recursive deadlock in orchestrator to verify full turn transition logic.
6. Windows CI Failure. Identified that regex `r"(?:^|/)(\d{1,3})(?=/|$)"` fails on Windows-style paths (`\`).

## Solution
### Implemented Fixes
- **Regex Refinement:** Updated `SessionPruningService._extract_turn_id` to use `r"(?:^|/)(\d{1,3})(?=/|$)"`.
- **Match Normalization:** Updated `SessionPruningService.prune` to check both raw and integer-normalized IDs.
- **Heuristic Resilience:** Updated validation failure check to use substring matching.
- **Platform Agnosticism:** Updated `SessionPruningService` to normalize paths to POSIX style during pruning analysis, ensuring regex and suffix checks work on all OSs.

### Prevention
- **Path Normalization Policy:** Core services performing string-based path analysis (regex, suffix checks) MUST normalize paths to POSIX style internally.
- **Regression Test:** Added `tests/suites/unit/core/services/test_session_pruning_windows.py` to cover cross-platform path handling.
