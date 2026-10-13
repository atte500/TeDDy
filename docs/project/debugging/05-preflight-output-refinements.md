# Bug: Misleading and mis-grouped `teddy start` preflight notifications
- **Status:** Resolved
- **Milestone:** N/A (ad-hoc)
- **Vertical Slice:** N/A (trivial presentation fix; follow-up to [00-33-refine-preflight-notifications.md](/docs/project/slices/00-33-refine-preflight-notifications.md))
- **Specs:** [interactive-session-workflow.md](/docs/project/specs/invariants/interactive-session-workflow.md)

## Symptoms

**Expected vs. actual.** `teddy start`'s preflight notification block is mis-formatted and carries a misleading line. Three observable defects:

1. The drift advice line and the shared disable-footer are separated by a stray blank line; they must read as ONE adjacent block, with the blank line relocated ABOVE the block (immediately after the `Checking configurations...` header).
2. An `API key valid! Model: ... | Agent: ...` line is printed although no API-key validity check ever runs.
3. The drift advice reads `To overwrite, run:`; the requested wording is `To update them, run:`.

**Current** (from the user's transcript):

```text
Checking configurations...
ℹ 6 prompts in .teddy/prompts/ differ from this version's defaults. To overwrite, run: teddy init prompts

You can disable this check in .teddy/config.yaml: checks.prompts.
API key valid! Model: openrouter/~deepseek/deepseek-flash-latest:nitro | Agent: Pathfinder
```

**Desired**:

```text
Checking configurations...

ℹ 6 prompts in .teddy/prompts/ differ from this version's defaults. To update them, run: teddy init prompts
You can disable this check in .teddy/config.yaml: checks.prompts.
```

**Minimal reproduction:** run `teddy start` in any workspace whose `.teddy/prompts/` or `docs/templates/` differs from the bundled defaults (or whose `docs/templates/` is missing a bundled template). Standalone MRE: `spikes/debug/01-preflight-output-mre.py`.

## Context & Scope

### Regressing Delta

No single regressing commit. This is a follow-up refinement on top of the just-shipped slice 00-33, which introduced the per-channel drift lines and the single shared disable-footer. The stray blank line originates from a literal trailing `\n` embedded in each drift string in [session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py) (`_display_drift_notification`, the `teddy init prompts` / `teddy init templates` branches around lines 429 and 445) which `typer.echo` doubles into a blank line. The `API key valid!` banner predates 00-33 (`_echo_config_success`, lines 620-646).

### Environmental Triggers

A workspace where `.teddy/prompts/` or `docs/templates/` has drifted from (or is missing) the bundled defaults, so the drift notification fires. A terminal that interleaves stderr and stdout -- `Checking configurations...` and the banner are stderr, while the drift line and the footer are stdout.

### Ruled Out

- Drift detection (`IInitUseCase.check_drift()` returning a `DriftReport`): correct.
- Footer wording, singular/plural selection, and canonical key ordering: correct.
- Notification toggle keys/defaults (`checks.prompts` / `checks.templates` / `checks.update`): correct.

## Diagnostic Analysis

### Causal Model

Three independent presentation defects live in `session_cli_handlers.py`; none touch the core domain or any Port signature:

1. **Mis-grouped blank line.** `_display_drift_notification` builds each advice string with a trailing literal `\n` (e.g. `f"ℹ {clause}. To overwrite, run: teddy init prompts\n"`) and passes it to `typer.echo`, which appends its own newline. The doubled newline deposits a blank line AFTER the drift line, which then separates it from the shared footer emitted immediately afterwards (`_display_checks_footer(fired)` in both `handle_new_session` and `handle_resume_session`).
2. **Misleading banner.** `_echo_config_success` unconditionally echoes `API key valid! Model: {resolved_model} | Agent: {canonical_agent_name}` on stderr. Nothing validates the key, and the resolved model and agent are already displayed by the planning header (`[{turn}] {name} | Waiting for {Agent} to respond...`) and the bullet-model line in `planning_service.py` -- so the banner is both unverified and redundant. It is called from `handle_new_session` and, on resume, from `_sync_and_display_session_meta`.
3. **Stale wording.** The drift advice tail is hardcoded as `To overwrite, run:`.
4. **Sibling mis-grouping (same class as #1).** `_display_update_notification` (line ~476) embeds the SAME trailing literal `\n` inside its styled advice (`f"ℹ A new version {latest} is available. To upgrade, run: {command}\n"`), depositing a stray blank line after the update notification. Per the user's no-debt directive it is fixed in-scope under the uniform rule (blank BEFORE the block, no trailing blank in the message).

### Discrepancies

- Removing the trailing `\n` could break the drift/footer unit tests if they pin the blank. (Resolved: `test_session_notification_toggles.py` asserts drift wording via substring membership and asserts the footer only when the footer helper is called in isolation, so relocating the blank is test-safe.)
- Deleting the banner could lose the model/agent display. (Resolved: both are re-displayed by the planning header and the bullet-model line, confirming the banner is redundant.)
- The desired blank sits between the stderr `Checking configurations...` header and the stdout drift block. (Resolved: the drift block is emitted on stdout, so the blank is emitted ONCE at the start of the stdout block — deterministic and directly testable, and it appears only when a notification actually fires.)
- Deleting `_echo_config_success` leaves three test surfaces referencing it. (Resolved: two unit tests exercise the function directly and a third patches it; they are a planned test migration bundled with the banner deletion, not a regression — the shadow replica proves the runtime behavior is correct.)

### Investigation History

1. Located the sole in-src emitters: drift strings (429/445), the shared footer (469/472), the banner (643/645), and `Checking configurations...` (562/1070). Confirmed slice 00-33 already shipped; this is a follow-up refinement.
2. Mapped the test surface: no test asserts the literal `API key valid`; two unit tests exercise `_echo_config_success` directly and a third patches it. Confirmed the model/agent are re-displayed elsewhere.
3. Authored the standalone MRE (`spikes/debug/01-preflight-output-mre.py`), which drives the REAL helpers through a stub container and captures stdout/stderr separately.
4. **Baseline reproduction (failing MRE).** Ran the MRE against the REAL helpers: it FAILED exactly as modelled. Captured stdout was `ℹ 6 prompts in .teddy/prompts/ differ from this version's defaults. To overwrite, run: teddy init prompts`, followed by a BLANK line, then `You can disable this check in .teddy/config.yaml: checks.prompts.`; captured stderr was `Checking configurations...` then `API key valid! Model: openrouter/~deepseek/deepseek-flash-latest:nitro | Agent: Pathfinder`. All three defects (A mis-grouped blank, B misleading banner, C stale wording) reproduce against production code. **Conclusion:** CONFIRMED (Items A/B/C).
5. **Shadow-file verification (zero-touch).** Created `spikes/debug/shadow_session_cli_handlers.py` — a faithful replica of ONLY the helpers the MRE exercises, with the fix applied (advice reworded to `To update them`; the trailing `\n` removed and ONE leading blank emitted inside `_display_drift_notification`; `_echo_config_success` deleted). Re-ran the MRE with `USE_SHADOW=1`: it **PASSED** (`MRE PASSED`, `EXIT=0`). Captured stdout was a leading blank, then `ℹ 6 prompts in .teddy/prompts/ differ from this version's defaults. To update them, run: teddy init prompts`, immediately followed by `You can disable this check in .teddy/config.yaml: checks.prompts.`; captured stderr was only `Checking configurations...`. All three defects are fixed by the modelled change, proven without a single write to `src/` or `tests/`. **Conclusion:** FIX VERIFIED (zero-touch).
6. **Systemic audit (Phase 4).** Enumerated the categorical signature (`\n"` string literals in `src/`). Within the inbound adapter layer the defect is confined to exactly THREE styled advices: the two drift strings and the update-notification string. Confirmed `_display_update_notification` (`:476`) carries the same trailing `\n` and fires EARLY in both `handle_new_session` (`:546`) and `handle_resume_session` (`:1063`), before `Checking configurations...`. Confirmed `canonical_agent_name` is referenced in the module ONLY at the import (`:21`) and inside `_echo_config_success` (`:645`), so the deletion orphans it. Confirmed neither `test_bug_24_model_override_on_resume.py` nor `test_session_cli_handlers_resume_meta.py` asserts the banner. **Conclusion:** root-cause category = "notification separator embedded inside the message string"; blast radius = 3 strings in one module; update-notification fix folded in per the no-debt directive; banner deletion ripples to 3 test surfaces.

## Solution

**Root cause (verified zero-touch).** Three independent presentation defects in [session_cli_handlers.py](/src/teddy_executor/adapters/inbound/session_cli_handlers.py), none touching the core domain or any Port signature:

1. **Mis-grouped blank line (Ask #1).** `_display_drift_notification` embeds a literal trailing `\n` in each advice string (lines ~429/445); `typer.echo` appends a second newline, depositing a blank line AFTER the drift line, which separates it from the shared footer emitted next.
2. **Misleading banner (Ask #2).** `_echo_config_success` (lines 620-646) unconditionally echoes `API key valid! Model: ... | Agent: ...` although nothing validates the key; the model and agent are already re-displayed by the planning header and the `• Model:` line.
3. **Stale wording (Ask #3).** The advice tail is hardcoded as `To overwrite, run:`.

**Proven fix.** In `_display_drift_notification`: (a) reword `To overwrite, run:` -> `To update them, run:`; (b) drop the trailing `\n` from each advice string and emit ONE leading `typer.echo("")` before the notification block (only when a notification actually fires) so the drift line and the shared disable-footer read as one adjacent unit, with the blank relocated to just after `Checking configurations...`; (c) delete `_echo_config_success` outright along with both of its call sites (`handle_new_session`, `_sync_and_display_session_meta`).

**Evidence.** `spikes/debug/shadow_session_cli_handlers.py` applies exactly this change as a zero-touch replica; the MRE (`USE_SHADOW=1`) flips from FAIL to PASS, reproducing the desired output end-to-end.

**Sibling fix (addressed in-scope).** Per the user's directive to fix friction directly rather than park it, `_display_update_notification` — which embedded the SAME trailing `\n` inside its styled advice — is fixed identically: the trailing `\n` is dropped and ONE leading blank is emitted before the line whenever it fires. The rule is now uniform across every preflight notification: **a blank separator BEFORE each notification block, and no trailing blank inside any notification string.**

**Test ripple (planned).** The banner deletion makes three existing test surfaces obsolete (`test_bug_16_model_override_message.py`, `test_echo_config_success_agent_casing.py`, and the `test_session_cli_handlers.py:387` patch target), which must be removed; the orphaned `canonical_agent_name` import is dropped. A regression test locks the final output shape (blank placement, `To update them` wording, banner absence).
