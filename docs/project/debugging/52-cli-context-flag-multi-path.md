# Bug: CLI `-c/--context` does not accept file paths directly (single-string option)

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** N/A
- **Specs:** [docs/architecture/adapters/inbound/cli.md](/docs/architecture/adapters/inbound/cli.md)

## Symptoms

**Expected:** `teddy start` accepts file path(s) as context directly via the `-c/--context` flag, including multiple paths without manual delimiter packing.
**Actual:** The option is declared as a single `Optional[str]`; multiple paths require comma-packing (`-c "a.py,b.md"`), and repeated occurrences silently overwrite (last one wins).

Minimal reproduction:
- `teddy start -c file1.py -c file2.py` → only `file2.py` is seeded into `session.context`.
- Enhancement request. User-aligned target interface (no breaking change): repeated `-c` flags AND comma-separated values within a single occurrence.

## Context & Scope

### Regressing Delta
None — this is an enhancement request, not a regression. The change is confined to the CLI adapter boundary in `src/teddy_executor/__main__.py`:
- Option declaration (lines 143–149): `context: Optional[str] = typer.Option(None, "--context", "-c", ...)`.
- Adapter split (line 165): `additional_context = context.split(",") if context else None`.

### Environmental Triggers
None — platform-independent CLI parsing behavior.

### Ruled Out
- `src/teddy_executor/adapters/inbound/session_cli_handlers.py` — already consumes `Optional[list[str]]`; no change needed.
- `src/teddy_executor/core/services/session_service.py` — consumes `options.additional_context` as a list; no change needed.
- All other comma-split sites (`textual_plan_reviewer_editor.py:598`, `textual_plan_reviewer_helpers.py:287`, `session_lifecycle_manager.py:224`) — internal UI/data parsing, not user CLI path input (systemic audit, Phase 4).

## Diagnostic Analysis

### Causal Model
The `start` command declares `context` as a single `Optional[str]` Typer option; Typer binds repeated occurrences by last-wins overwrite. At the adapter boundary, the single string is comma-split once (`context.split(",")`) and handed to `handle_new_session(additional_context: Optional[list[str]])` → `SessionOptions.additional_context` → `SessionService.create_session`. The entire multiplicity constraint therefore lives at the CLI declaration + split boundary; the downstream contract is already list-typed.

### Discrepancies
- README "Optional flags" documents `--model / -m`, but `-m` is actually `--message` (the model flag has no short alias). Doc defect. (Resolved: corrected in README during the contract update for this change.)
- cli.md `start` contract omits `--context`/`-c` entirely. Doc gap. (Resolved: signature and behavior documented during this session.)

### Investigation History
1. Hypothesis: `-c` may already support multiplicity. Observation: single `Optional[str]` with last-wins overwriting; comma-split at the boundary. Conclusion: enhancement required at the CLI boundary only.
2. Hypothesis: downstream requires changes. Observation: `handle_new_session` and `SessionOptions.additional_context` are already `Optional[list[str]]`. Conclusion: change confined to `__main__.py`.
3. Hypothesis (Phase 4 audit): other delimiter-splits of user path input may exist. Observation: only `__main__.py:165` splits user CLI path input; no repeatable list-typed Typer option precedent exists; tests drive the CLI via `CliRunner` (no direct signature binding to the option type). Conclusion: introducing the repeatable-option pattern is safe; signature-drift risk limited to `--help` string assertions.
4. Hypothesis (TDD): a RED regression test for repeated `-c` flags fails against the unmodified CLI while the comma-compat test passes. Observation (RED): `test_start_command_accepts_repeated_context_flags` failed exactly on the first-path assertion — `session.context` contained only the second `-c` occurrence (last-wins overwrite confirmed) — while `test_start_command_accepts_comma_separated_context` passed. After applying the fix (`Optional[list[str]]` declaration + flattened per-occurrence comma split with `strip()`), both new tests pass (GREEN), all 4 tests in `test_cli_context_flag.py` pass, and the full suite is green (1258 passed, 5 skipped). Conclusion: fix empirically verified; backward compatibility preserved; no regressions.

## Solution

**Root cause (enhancement):** The `-c/--context` flag is declared as a single `Optional[str]`, forcing users to comma-pack multiple paths and silently overwriting repeated occurrences.

**Fix (implemented & verified):**
1. Changed the declaration in `src/teddy_executor/__main__.py` to `Optional[list[str]]` so Typer collects repeated occurrences (`-c a -c b`).
2. At the adapter boundary, flattened per-occurrence comma splits (`[path.strip() for occurrence in context for path in occurrence.split(",") if path.strip()]`) — preserving backward compatibility for `-c "a,b"`.
3. Updated help text, README, and the cli.md `start` contract.

**Verification evidence:** RED — `test_start_command_accepts_repeated_context_flags` failed against unmodified code (first path absent; last-wins overwrite confirmed) while the comma-compat guard passed. GREEN — both new tests pass, all 4 tests in `test_cli_context_flag.py` pass, and the full suite is green (1258 passed, 5 skipped).

**Preventative measures (class-level):** Prefer list-typed (repeatable) Typer options for any user-supplied multi-value input, and document the comma-in-path limitation wherever delimiter-splitting of path input is retained. No other instances of this category exist in the codebase (audited).
