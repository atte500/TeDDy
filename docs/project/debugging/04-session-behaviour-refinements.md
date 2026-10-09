# Bug: Session Init, Prompt/Template Divergence & Agent-Name Casing

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** [00-32-session-behaviour-refinements](/docs/project/slices/00-32-session-behaviour-refinements.md)
- **Specs:** N/A

## Symptoms

Six behaviour refinements were requested. Three read as technical defects, two as missing notifications, one as a display defect.

1. **Templates auto-scaffolded on first startup (defect).**
   - *Expected:* `docs/templates/` is created ONLY by the explicit `teddy init templates` command.
   - *Actual:* A bare `teddy init` AND `teddy start`/`teddy resume` auto-create `docs/templates/` (via `InitService.ensure_initialized()` folding in `_init_templates(overwrite=False)`).

2. **Session file holds the raw prompt, not the composed system prompt (defect).**
   - *Expected:* The session-root prompt file (e.g. `.teddy/sessions/<name>/pathfinder.xml`) contains the FULL composed system prompt actually sent to the model: the `Agent Name: …` header + the agent XML + the appended MRP base prompt.
   - *Actual:* `SessionService.create_session` writes only the RAW agent-prompt content returned by `_resolve_agent_prompt`.

3. **No divergence notification for `.teddy/prompts/` (missing notification).**
   - *Expected:* When `.teddy/prompts/*.xml` differ from the bundled defaults, `teddy start` shows a yellow message telling the user to run `teddy init prompts` to update to the latest version.
   - *Actual:* No comparison is performed; no message is emitted.

4. **No divergence/missing notification for templates (missing notification).**
   - *Expected:* The same check for `docs/templates/*.md`, including the case where some templates are MISSING, with a directive to run `teddy init templates`.
   - *Actual:* No comparison; no message.

5. **No config toggles (missing feature).**
   - *Expected:* `config.yaml` exposes independent switches to disable the prompt/template check and the update check.
   - *Actual:* Neither switch exists.

6. **Agent name casing not normalized (display defect).**
   - *Expected:* `teddy start -a PATHFINDER` displays `Agent: Pathfinder` and `Waiting for Pathfinder to respond...`.
   - *Actual:* Both strings display `PATHFINDER`.
   - *Repro:* `teddy start -a PATHFINDER` → banner shows `Agent: PATHFINDER`; planning header shows `Waiting for PATHFINDER to respond...`.

## Context & Scope

### Regressing Delta

- **Item 1:** `f0c2615c feat(templates-init): auto-scaffold docs/templates on bare init` extended `InitService.ensure_initialized()` to call `_init_templates(overwrite=False)` (introduced by `0ed7dd77 feat(templates-init): implement template copy support in InitService`). This made templates auto-created on `teddy start`/`teddy resume`/bare `teddy init`.
  - **Reversal note:** This auto-scaffold behaviour was an intentional, documented decision in the COMPLETED slice [`03-03-templates-and-init`](/docs/project/slices/03-03-templates-and-init.md) ("Bare `teddy init` also creates `docs/templates/`; `teddy start`/`teddy resume` auto-create it non-destructively"). The Item 1 request REVERSES that decision: templates must be created only by the explicit `teddy init templates` command. The slice doc and its acceptance test (`tests/suites/acceptance/test_templates_auto_init.py`) must be updated, not merely the wiring.
- **Items 2–5:** Absence-of-feature — no regressing commit; never implemented.
- **Item 6:** No regressing commit — the raw `-a` value has always been displayed verbatim at `session_cli_handlers.py` (the `Agent: {agent}` banner line) and `planning_service.py:40`, and persisted verbatim into `meta.yaml["agent_name"]`.

### Environmental Triggers

- None OS-specific. All six behaviours are reproducible in a clean temporary project directory on any platform.

### Ruled Out

- **`PromptManager.fetch_system_prompt` casing.** Already uses `agent_name.capitalize()`; it is NOT the source of the all-caps display.
- **Prompt-file resolution casing.** Already casefold-matched (slice `00-03-cli-arg-normalization`); resolution works for any casing. Only the *displayed/persisted* casing is wrong (Item 6).
- **`prompts.py` lookup.** Already case-insensitive; unrelated to the defect.

## Diagnostic Analysis

### Causal Model

**Item 1.** `InitService.ensure_initialized()` is the single entry point invoked on every startup path (`teddy init` bare, `teddy start`, `teddy resume`, and `SessionService._prepare_session_context`). It unconditionally calls `_init_config_dir`, `_init_prompts`, AND `_init_templates(overwrite=False)`. Because `_init_templates` create-only-writes the 11 bundled templates into `docs/templates/`, any first startup scaffolds the directory even though the user never asked for it. The explicit, intent-bearing path (`ensure_templates_initialized(overwrite=True)` via `teddy init templates`) is therefore indistinguishable from the implicit startup path. **Verified fix (Shadow File):** removing the `_init_templates(overwrite=False)` call (and the trailing `Templates:` summary segment) from `ensure_initialized()` is sufficient — the shadow replica at `spikes/debug/shadow_init_service.py` flips the MRE's Item 1 to PASS while the control (explicit `ensure_templates_initialized(overwrite=True)`) still copies 11/11. Proven without modifying `src/`.

**Item 2.** At session creation, `SessionService.create_session` calls `_resolve_agent_prompt(agent_name)`, which reads the raw `.teddy/prompts/<agent>.xml` and writes that raw content to `{session_root}/{prompt_filename}`. The composed system prompt is assembled lazily and only in-memory by `PromptManager.fetch_system_prompt` (called later during planning / execution), which prepends `Agent Name: …` and appends `MRP.xml`. The composed string is never persisted, so the session file is the raw agent XML, not the true model input. **Design constraint:** `PromptManager._resolve_agent_prompt_content` reads the SESSION ROOT prompt file FIRST (before `.teddy/prompts/`), so naively writing the composed prompt to `{session_root}/{prompt_filename}` would cause the next `fetch_system_prompt` call to read the already-composed prompt and compose it again (double `Agent Name:` header + duplicated MRP). The fix must resolve this ordering — e.g. persist the composed prompt under a distinct filename, or write it at a lifecycle point after resolution — which is a slice-level design decision.

**Items 3/4.** No component ever diffs a user file against its bundled default. `InitService` only *copies* bundled resources; it never compares. `PromptManager` only resolves/assembles. Therefore divergence (edited) and absence (deleted) are both invisible, and no notification can fire.

**Item 5.** `config.yaml` ships only execution/read/research/yolo/pruning/llm keys. `IConfigService.get_setting` exists, but there are no check-related keys to read and no gating logic that consults them.

**Item 6.** The `-a/--agent` value flows verbatim: `__main__.start(agent=…)` → `handle_new_session(agent=…)` → both (a) the CLI banner `msg += f" | Agent: {agent}"` in the config-success echo, and (b) `SessionOptions.agent_name` persisted to `meta.yaml["agent_name"]`. During planning, `PromptManager.resolve_agent_metadata` reads `meta["agent_name"]` (raw) and `planning_service.py:40` interpolates it into `Waiting for {agent_name} to respond...`. The agent-prompt resolution itself is casefold-insensitive, so nothing errors — the raw casing simply leaks into every display surface. The canonical authority for casing is the resolved prompt file stem (e.g. `pathfinder.xml` → `Pathfinder`).

### Discrepancies

- Observed all-caps `Agent: PATHFINDER` while `fetch_system_prompt` already calls `.capitalize()`. Conflict: the system-prompt header should be title-cased. (Resolved: the CLI banner and the planning header do NOT use `fetch_system_prompt`; they interpolate the raw `-a` value / raw `meta["agent_name"]`.)
- Request text referenced `.teddy/session/<session-name>/pathfinder.xml`, but the runtime persists `.teddy/sessions/<session-name>/` (plural). (Resolved: canonical root is `.teddy/sessions/` per `session_repository.py` and the runtime output; the request used shorthand.)

### Investigation History

1. **Hypothesis:** Templates are auto-created on startup. **Observation:** `InitService.ensure_initialized()` calls `_init_templates(overwrite=False)`; reached from `__main__.py:149/258`, `session_cli_handlers.py:441`, `session_service.py:82`. **Conclusion:** CONFIRMED (Item 1). Delta `f0c2615c`.
2. **Hypothesis:** The composed system prompt is written to the session file. **Observation:** `SessionService.create_session` writes the RAW `_resolve_agent_prompt` content; `fetch_system_prompt` is only ever used in-memory. **Conclusion:** CONFIRMED that the composed prompt is NOT persisted (Item 2).
3. **Hypothesis:** A divergence/missing check exists for prompts/templates. **Observation:** `git grep` for "diverge/differs/out of date" finds only unrelated agent-XML prose; `config.yaml` has no check keys. **Conclusion:** CONFIRMED absent (Items 3/4/5).
4. **Hypothesis (Item 6):** the all-caps originates in `fetch_system_prompt`. **Observation:** that method already `.capitalize()`s; the raw value is used at `session_cli_handlers.py:527` and `planning_service.py:40`. **Conclusion:** REJECTED the hypothesis; Item 6 is a display/persisted-state defect, not a prompt-assembly defect.
5. **Hypothesis (Items 1/2/6 reproduce against real adapters).** **Observation:** `spikes/debug/04-session-behaviour-refinements-mre.py` — a self-contained script driving the REAL `LocalFileSystemAdapter` + REAL `InitService`/`SessionService` from `src/` — exited 1, printing `[FAIL] Item 1` (auto-created `docs/templates/`), `[FAIL] Item 2` (session prompt holds the raw agent XML, no `Agent Name:` header), `[FAIL] Item 6` (`meta.agent_name` persisted verbatim as `'PATHFINDER'`), and `[PASS] Item 1b` (explicit `ensure_templates_initialized(overwrite=True)` copied 11/11 — positive control). **Conclusion:** CONFIRMED — the three defects reproduce empirically against production wiring; the causal model holds end-to-end. Items 3/4/5 remain absence-of-feature (not expressible as a failing assertion against existing API surface).
6. **Hypothesis (Item 1 fix resolves the defect without touching `src/`).** **Observation:** with `USE_SHADOW=1`, the MRE loads `spikes/debug/shadow_init_service.py` — a faithful replica whose `ensure_initialized()` drops the `_init_templates(overwrite=False)` call and the trailing `Templates:` summary segment. Re-run output: `[PASS] Item 1` (no `docs/templates/` created), `[PASS] Item 1b` (control still 11/11), `[FAIL] Item 2` / `[FAIL] Item 6` (unchanged — not addressed by this shadow). **Conclusion:** CONFIRMED — removing the `_init_templates` call from `ensure_initialized()` is the complete, sufficient fix for Item 1, and it is verified zero-touch (no `src/` modification). Items 2/6 require slice-level design decisions and remain open.

## Solution

**Root cause (verified).** Six refinements, three defect classes:

- **Item 1 (defect, verified fix):** `InitService.ensure_initialized()` unconditionally calls `_init_templates(overwrite=False)`, so `docs/templates/` is auto-scaffolded on `teddy init`/`start`/`resume`. Removing that call (and the trailing `Templates:` summary segment) from `ensure_initialized()` is the complete, sufficient fix — proven via the shadow replica (`spikes/debug/shadow_init_service.py`) without touching `src/`. The explicit `teddy init templates` command (`ensure_templates_initialized(overwrite=True)`) is unaffected. Note this REVERSES a documented decision in the completed slice [`03-03-templates-and-init`](/docs/project/slices/03-03-templates-and-init.md); its acceptance test `tests/suites/acceptance/test_templates_auto_init.py` must be updated.
- **Item 2 (defect, design-sensitive):** `SessionService.create_session` persists the RAW agent prompt to the session root; the composed system prompt (`Agent Name: …` + agent XML + `MRP.xml`) is only ever assembled in-memory. `PromptManager._resolve_agent_prompt_content` reads the session root FIRST, so naively writing the composed prompt there would double-compose. **Resolved design (approved — Option A):** split `fetch_system_prompt`'s compose/read roles — compose once at session creation and on agent switch, persist the composed prompt to the session root, then return it verbatim on every later turn (no detection; a missing file lazily recomposes). The legacy `<response_format>` skip moves into the compose step.
- **Item 6 (defect, display/persistence):** the raw `-a` value is interpolated verbatim at the CLI banner (`session_cli_handlers.py`) and the planning header (`planning_service.py`) and persisted verbatim to `meta.yaml["agent_name"]`. Canonical casing authority is the resolved prompt file stem (e.g. `pathfinder.xml` → `Pathfinder`).

**Systemic measures (handoff slice):** Items 3/4 (no drift detection between bundled defaults and user prompts/templates) and Item 5 (no independent config toggles) are absence-of-feature. The full remediation — divergence checks, config switches, composed-prompt persistence, and agent-name canonicalization — spans multiple subsystems and is delivered as a single Vertical Slice: [`00-32-session-behaviour-refinements`](/docs/project/slices/00-32-session-behaviour-refinements.md).
