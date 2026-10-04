# Bug: editor-empty-config-no-prompt

- **Status:** Resolved
- **Milestone:** N/A
- **Vertical Slice:** [00-26-editor-setup-decoupling.md](/docs/project/slices/00-26-editor-setup-decoupling.md) (fix; originating feature: [03-01-editor-validation-and-discovery.md](/docs/project/slices/03-01-editor-validation-and-discovery.md))
- **Specs:** [editor-validation-and-discovery.md](/docs/project/specs/editor-validation-and-discovery.md)

## Symptoms
Expected: With the bundled default `editor: ""` (unconfigured), starting an
interactive session (`teddy start`) should trigger the editor selection prompt
during preflight (discover editors → prompt → persist the choice).

Actual: The selection prompt does not appear.

Minimal reproduction steps:
1. Ensure the effective config does not resolve a usable `editor`
   (bundled baseline is `editor: ""`).
2. Run `teddy start` in interactive mode.
3. Expected: "No editor configured..." warning + "Editor Setup" + editor list
   + selection prompt. Actual: no prompt.

## Context & Scope
### Regressing Delta
CONFIRMED (isolated fresh-project MRE, Turn 5): the empty `editor` value is
NOT the cause. The suppression is the interaction of two
recently-added features:
- `feat(yolo-default-config)` (221f0166, 7f20c1a5): `_resolve_yolo()` falls back
  to the `yolo_default` config setting when no `--yolo`/`--no-yolo` flag is
  passed, and `__main__.start`/`resume` compute
  `interactive = not (_resolve_yolo(...) or pipeline or yes or ...)`.
- `feat(editor-validation-and-discovery)` (db2dd0d4): `_run_cli_preflight_check`
  runs `_validate_editor_config` ONLY when `interactive` is True.

When the effective config sets `yolo_default: true`, `interactive` resolves to
False and the editor gate is skipped — independent of the (falsy) `editor` value.

### Environmental Triggers
The reproducer's OWN effective config (`CWD/.teddy/config.yaml`) sets
`yolo_default: true` (bundled baseline is `yolo_default: false`). Running
`teddy start` with no explicit `--no-yolo/-n` therefore resolves to
non-interactive mode locally, suppressing the editor prompt.

The effective config also DRIFTED during this session: the Turn 3 dump showed a
BARE `editor:` (null -> pruned on merge), while the Turn 4 MRE resolved it to
`'codium'`. This write is an environmental artifact (see Investigation History
#6) and is orthogonal to the defect mechanism.

### Ruled Out
- The `editor` VALUE is not defective: a faithful isolated MRE (fresh temp
  project, bundled defaults `editor: ""`) shows the gate DOES prompt when
  reached (`prompt invoked == True`).
- `YamlConfigAdapter` merge/resolution: a falsy editor correctly routes to the
  discovery-prompt branch.
- `_prompt_for_editor_selection` / `_prompt_for_custom_editor`: verified to
  persist the correct value when invoked.
- The `-c`/agent/context CLI plumbing, health checks, and update-checker:
  untouched by the suppression.

## Diagnostic Analysis
### Causal Model
1. `teddy start` (no `-y`/`-n`) computes
   `interactive = not (_resolve_yolo(None, config) or pipeline or yes or ...)`.
2. `_resolve_yolo(None, config)` returns `bool(config.get_setting("yolo_default",
   False))`. The effective config has `yolo_default: true`, so this is True and
   `interactive` becomes False.
3. `_run_cli_preflight_check(interactive=False)` therefore SKIPS
   `_validate_editor_config` entirely, so no discovery/selection prompt fires.
4. VERIFIED via a clean, isolated fresh-project MRE (only `typer.prompt`
   stubbed): with bundled defaults (`editor: ""`, `yolo_default: false`) and the
   gate invoked, the selection prompt DOES fire and persists the chosen editor
   (`prompt invoked == True` -> 'nvim'). With `yolo_default: true` the gate is
   skipped entirely (`prompt invoked == False`). The `editor` value is therefore
   NOT defective; the SOLE suppressor is `interactive == False` (driven by
   `yolo_default: true`).
5. Spec consequence: spec §2/§4 mandate that non-interactive runs (`-y`/`-p`/
   `--yolo`/`--pipeline`) bypass ALL editor checks. The observed behavior is
   therefore SPEC-COMPLIANT, not a code defect: with `yolo_default: true` the
   session is non-interactive by definition, so skipping the editor gate is
   intended. The remaining question is a PRODUCT decision (should editor setup
   still run once in non-interactive mode?), which requires user alignment — not
   a bug fix.
6. SHADOW-VERIFIED FIX: replicating `_run_cli_preflight_check` with the editor
   gate DECOUPLED from `interactive` (everything else identical) and driving it
   with the SAME `interactive=False` input flips the outcome (`prompt invoked`
   False -> True; editor '' -> 'nvim'). The `interactive` guard is therefore the
   SOLE suppressor. CAVEAT: truly headless contexts (pipeline/CI, `-m`
   one-shots) must still avoid blocking on a prompt, so the production fix is a
   PRODUCT/spec decision (e.g., gate editor setup on TTY-availability rather
   than on the yolo approval flag) rather than a mechanical guard removal.
7. SPEC GAP CONFIRMED (Turn 13): the `interactive` flag conflates approval-mode
   (auto-approve actions) with input-availability (does the session still read
   from the terminal?). `handle_new_session` prompts for the opening message
   whenever `-m` is absent REGARDLESS of `interactive`, so a `-y` /
   `yolo_default: true` session remains terminal-interactive — yet
   `_run_cli_preflight_check` skips the one-time editor setup on
   `interactive == False`. Decoupling the editor setup from the approval flag
   (gating it on terminal-availability while preserving truly-headless
   pipeline/CI/one-shot paths) is therefore a SPEC CORRECTION, aligned with the
   user's direction (A).
8. REFINED CRITERION (Turns 20-21, user-aligned): the gate must be keyed on
   "the session will actually READ the terminal", not on bare TTY-availability.
   A fully-specified batch run (`-y` WITH `-m`) reads nothing and must NOT
   prompt, while a yolo run WITHOUT `-m` (which still blocks on the opening
   prompt) MUST. Criterion:
   `setup_editor = system_env.isatty() AND (not pipeline) AND (interactive OR message is None)`.
   Additionally (debt folded in-slice per the user): the redundant hidden
   non-interactive aliases (`--yes`/`--no-interactive`/`--non-interactive`) are
   retired, collapsing `interactive` to `not (_resolve_yolo(...) or pipeline)`
   so it means approval-only.

### Discrepancies
- The implemented gate appears to prompt on empty editor, yet the user reports
  no prompt. Conflict: the surface code should produce the prompt. (resolved:
  the clean isolated MRE proved `editor: ""` DOES prompt when the gate is
  reached; the gate is skipped because `interactive == False`, driven by
  `yolo_default: true`. The editor value is not implicated.)
- The Turn 3 dump showed a BARE `editor:` (null -> pruned on merge), yet the
  Turn 4 MRE resolved `get_setting("editor") == 'codium'` and reported
  `'editor' in cfg._config == True`. Conflict: an empty/pruned editor should
  yield None/falsy, not a concrete 'codium'. (resolved: the effective user
  config was rewritten on disk between the two reads — mtime 10:30:36, AFTER the
  active session dir was created at 10:29:17 and WITHOUT producing any new
  session dir. `handle_new_session` runs the editor gate BEFORE session
  creation, so a `teddy start` selection would have stamped the file before
  10:29:17, not at 10:30:36. The ONLY code path that writes the `editor` key is
  `_persist_editor_choice`, reachable solely from the interactive prompt.
  Therefore the drift is an environmental artifact — an interactive
  `resume -n` / manual edit performed OUTSIDE the run under investigation — and
  is orthogonal to the defect mechanism. The read-path resolution itself
  (`set_setting` -> in-memory cache sync) was verified correct in the clean MRE.)

### Investigation History
1. Read bundled config.yaml, session_cli_handlers.py, console_tooling.py,
   yaml_config_adapter.py. Observation: bundled `editor: ""`; gate prompts on a
   falsy editor. Conclusion: must observe the real runtime path.
2. Read __main__.py, the editor spec, the preflight/editor tests, and the
   git-log of the wiring files. Observation: `interactive` is derived from
   yolo/pipeline flags; the editor gate is reached only when
   `interactive and not errors`. Conclusion: candidate suppression points are
   (a) effective non-empty editor, (b) interactive=False, (c) LLM errors.
3. Dumped the effective config (`CWD/.teddy/config.yaml`) and git-logged the
   bundled config. Observation: the user config sets `yolo_default: true`
   (bundled = false) and a bare `editor:` (null -> pruned on merge); bundled
   `editor: ""` landed in b12542da. Conclusion: the empty editor is a red
   herring; leading cause is `yolo_default: true` -> non-interactive -> editor
   gate skipped. Probe spawned to confirm the `interactive` computation.
4. Ran the MRE against the REAL effective config. Observation: the editor gate
   is NOT reached (`interactive=False`, driven by `yolo_default=True`), BUT the
   effective `editor` resolved to `'codium'` (non-empty) — contradicting the
   Turn 3 dump of a bare `editor:`. Conclusion: the yolo_default short-circuit
   is confirmed for the interactive gating; the `codium` value means the MRE did
   NOT reproduce the EXACT `editor == ''` scenario. Must (a) explain the config
   rewrite and (b) reproduce faithfully with an empty editor before asserting
   the root cause.
5. Ran a clean, isolated fresh-project MRE (temp dir, bundled defaults, only
   `typer.prompt` stubbed). Observation: Case A (`editor: ""`,
   `yolo_default: false`, gate invoked) -> `prompt invoked == True`, persists
   'nvim'; Case B (`yolo_default: true`, gate skipped) -> `prompt invoked ==
   False`. Conclusion: `editor: ""` prompts correctly in interactive mode; the
   sole suppressor is `interactive == False` via `yolo_default: true`. Root
   mechanism CONFIRMED.
6. Forensic probe of `.teddy/` to provenance the `codium` drift.
   Observation: `.teddy/config.yaml` mtime = 10:30:36, `.update_cache.json`
   mtime = 10:30:13, `init.context` mtime = 10:28:33; the active session dir
   `20261004_102917-...` was created at 10:29:17 and NO new session dir exists
   around 10:30. Conclusion: the `editor: codium` write happened AFTER this
   session's creation, independent of it — consistent with an interactive
   `resume -n` run (or a manual edit) executed outside the run under
   investigation, NOT with any automatic writer (the only `editor` writer is the
   interactive prompt's `_persist_editor_choice`; the gate runs before session
   creation, so a `start` selection cannot explain a post-creation mtime). The
   drift is environmental and orthogonal; the `editor` VALUE is not implicated
   in the suppression.
7. Shadow-File verification (Zero-Touch, Phase 2 Step 6): replicated
   `_run_cli_preflight_check` into `spikes/debug/shadow_session_cli_handlers.py`
   with a SINGLE behavioural change — the editor gate decoupled from
   `interactive` — and drove BOTH the real and the shadow preflight with the
   identical input (`interactive=False`; fresh temp project `editor: ""` +
   `yolo_default: true`), stubbing only terminal input (`typer.prompt`).
   Observation: REAL -> `prompt invoked == False` (editor stays ''); SHADOW ->
   `prompt invoked == True` (editor persisted to 'nvim'). Conclusion: the
   `interactive` guard is the SOLE suppressor; decoupling the one-time editor
   setup from the approval flag flips the outcome. Fix direction empirically
   PROVEN without touching `src/`.
8. Read `session_cli_handlers.py` (lines 1-720) to verify the user's claim that
   a yolo session still prompts for the opening message. Observation:
   `handle_new_session` resolves a missing initial message via
   `user_interactor.ask_question("What are we working on?")` whenever
   `message is None`, UNCONDITIONALLY on the `interactive` flag (only
   `pipeline` raises `ValueError` when `-m` is absent). Conclusion: a `-y` /
   `yolo_default: true` session IS input-interactive at the terminal boundary
   (it blocks on the opening prompt when `-m` is omitted), yet the editor gate
   is skipped because `interactive == False`. This CONFIRMS the user's
   diagnosis — `interactive` conflates two orthogonal concerns: (a) auto-approval
   of actions and (b) whether the session still reads from the terminal — and
   the one-time editor setup is mis-coupled to (a). The skip is a SPEC GAP, not
   intended behavior.
9. Systemic Audit (Phase 4). Observation: spec §2/§4 EXPLICITLY mandate that
   non-interactive runs bypass editor checks, so the current behavior is
   spec-compliant and the fix is a spec CORRECTION; `_run_cli_preflight_check`
   has exactly three callers (`handle_new_session` and `handle_resume_session`,
   both `interactive=interactive`; and `handle_plan_generation`, a one-shot
   `interactive=False`); `ISystemEnvironment` exposes NO terminal-availability
   capability (`which`/`get_env`/`run_command`/`create_temp_file`/`delete_file`),
   though direct `sys.stdin.isatty()` precedent exists in outbound adapters and
   `core/utils/terminal.py` checks `sys.stdin.isatty()` internally (not a
   reusable predicate). Conclusion: the fix is a decoupling plus a
   terminal-availability seam; it touches a Port (Contract), the CLI wiring, the
   spec, and tests, so it is NON-TRIVIAL and is handed off as Vertical Slice
   00-26.
10. Alignment locked (Turns 11-21). The user confirmed the mechanism, chose the
   decouple direction, and refined the gating criterion: editor setup must NOT
   run for a fully-specified batch run (`-y -m`) but MUST run for a yolo run
   without `-m` (`setup_editor = isatty() AND not pipeline AND (interactive OR
   message is None)`). The user also directed that the `interactive`-conflation
   debt be addressed in-slice and agreed to retire the redundant hidden
   non-interactive CLI aliases. Conclusion: scope locked; Slice 00-26 is being
   revised to fold in the debt; the PROJECT.md debt entry is removed.

## Solution

### Root Cause
The one-time editor-setup gate in `_run_cli_preflight_check`
(`session_cli_handlers.py`) is keyed on the session `interactive` flag.
`__main__.py` computes that flag as
`not (_resolve_yolo(yolo, config) or pipeline or yes or no_interactive or
non_interactive)`, so the single flag conflates two orthogonal concerns:
(1) **approval mode** (are actions auto-approved?) and (2) **terminal/input
availability** (does the session still read from the terminal?).

`handle_new_session` prompts for the opening message whenever `-m` is absent,
REGARDLESS of `interactive`. A `-y` / `yolo_default: true` session therefore
REMAINS terminal-interactive — yet `_run_cli_preflight_check(interactive=False)`
skips the editor gate entirely. Hence a yolo-default user never sees the editor
selection prompt, independent of the (falsy) `editor` value. The bundled
`editor: ""` is a red herring. This is a SPEC GAP (spec §2/§4 had mandated the
skip), not intended behaviour.

### Proven Fix (Shadow-verified)
Decouple the one-time editor setup from the approval flag by keying it on a
dedicated "will the session read the terminal?" signal rather than on `--yolo`.
The verified criterion is
`setup_editor = system_env.isatty() AND (not pipeline) AND (interactive OR message is None)`:
this fixes the reported bug (yolo without `-m` still prompts for the opening
message, so editor setup runs), keeps fully-specified batch runs (`-y -m`) and
headless runs (pipeline, non-TTY) prompt-free, and preserves the
interactive-with-message behaviour. The Shadow-File verification held all inputs
constant and changed ONLY the gate: the REAL preflight skipped it (no prompt),
while the decoupled shadow fired the prompt and persisted the editor — proving
the `interactive` guard is the SOLE suppressor. Fix delivered via Vertical Slice
[00-26-editor-setup-decoupling.md](/docs/project/slices/00-26-editor-setup-decoupling.md).

### Systemic Preventative Measure
Introduce a dedicated terminal-availability seam
(`ISystemEnvironment.isatty()`) and a distinct `setup_editor` signal so that no
future one-time, TTY-bound configuration step is ever gated on the approval/yolo
flag; `interactive` becomes approval-only. As part of the same slice (per the
user's request to address the debt directly rather than log it separately), the
redundant hidden non-interactive CLI aliases (`--yes`/`--no-interactive`/
`--non-interactive`) are retired so `interactive` collapses to
`not (_resolve_yolo(...) or pipeline)`, and the headless/automated path is
documented as `-y` (or non-TTY stdin). The separate PROJECT.md debt entry is
therefore removed — the debt is resolved in-slice.
