# Slice: Editor-Setup Decoupling from Approval Mode

- **Status:** Planned
- **Milestone:** N/A (ad-hoc regression fix; amends the Milestone 3 editor spec)
- **Specs:** [editor-validation-and-discovery.md](/docs/project/specs/editor-validation-and-discovery.md)
- **Prototype:** N/A — Shadow-File verification recorded in [Case File 67](/docs/project/debugging/67-editor-empty-config-no-prompt.md)
- **Component Docs:** [cli.md](/docs/architecture/adapters/inbound/cli.md), [system_environment.md](/docs/architecture/core/ports/outbound/system_environment.md)
- **Scope Slug:** `editor-setup-decoupling`

## Business Goal

Run the one-time editor-selection setup whenever a session will actually READ
the terminal — including a `--yolo` / `yolo_default: true` run that still blocks
on the opening-message prompt — so that yolo users can configure their editor
through the discovery prompt without disabling yolo, while keeping fully
specified batch runs (`-y -m`), truly headless runs (`--pipeline`, non-TTY
stdin), and one-shot commands prompt-free.

## Scenarios

> As a yolo-default user running `teddy start` on a terminal, I want the editor selection prompt to appear once so that I can configure my editor without disabling yolo.

```gherkin
Given an effective config with yolo_default: true and an unconfigured editor: ""
And the command runs on a real terminal (stdin is a TTY)
When I run teddy start without -m
Then the preflight shows the "No editor configured" warning and the "Editor Setup" prompt
And my numbered selection is persisted to .teddy/config.yaml
```

> As a user running a fully-specified batch session, I want no editor prompt so that an automated, fire-and-forget run never blocks.

```gherkin
Given an unconfigured editor: ""
And the command runs on a real terminal (stdin is a TTY)
When I run teddy start -y -m "do the thing"
Then the editor gate is skipped and no prompt appears
```

> As a CI/pipeline operator, I want no editor prompt so that automation never blocks.

```gherkin
Given an unconfigured editor: ""
When I run teddy start --pipeline -m "do the thing" (or stdin is not a TTY)
Then the editor gate is skipped and no prompt appears
```

## Edge Cases

- **Pipeline**: If `--pipeline` is set, then skip editor setup, because a pipeline run must never block on a prompt.
- **Fully-specified batch run**: If the run is non-interactive (`--yolo` / `yolo_default: true`) AND a message was supplied (`-m`), then skip editor setup, because the session will never read the terminal (no opening prompt, no approval loop).
- **Non-TTY stdin**: If `sys.stdin.isatty()` is False (CI, piped, redirected), then skip editor setup, in order to avoid hanging on an unanswerable prompt.
- **One-shot command**: If `handle_plan_generation` runs, then keep skipping editor setup, because a one-shot plan generation is not an interactive session.
- **Already configured / disabled**: If `editor` resolves on PATH or equals the `"disabled"` sentinel, then no prompt fires, because the 03-01 flow already handles these.

## Key Unknowns

- [x] [Functional] Should editor setup run for `teddy start -y -m "..."` on a TTY (where no opening prompt fires)? – Resolution: NO (user-aligned 2026-10-04). A `-y -m` run is fully specified and batch (no opening prompt, no approval loop), so it must NOT prompt. The gate keys on "the session will actually read the terminal", not on bare TTY-availability.
- [x] [Technical] Does the TTY check belong on `ISystemEnvironment` (new `isatty()` member) or reuse an existing seam? – Resolution: add `isatty()` to `ISystemEnvironment`; no reusable terminal-availability predicate exists today (`core/utils/terminal.py` only restores cooked mode).
- [x] [Technical] Do the hidden `--yes` / `--no-interactive` / `--non-interactive` flags still force a headless skip? – Resolution: NO — the redundant hidden aliases are RETIRED entirely (user-aligned 2026-10-04); `-y` (or non-TTY stdin) becomes the documented headless path, so `interactive` collapses to `not (_resolve_yolo(...) or pipeline)`.

## Implementation Plan

Root cause (Bug 67): `_run_cli_preflight_check` gates the one-time editor setup on
the session `interactive` flag, which `__main__.py` computes as
`not (_resolve_yolo(...) or pipeline or yes or no_interactive or non_interactive)`.
That flag conflates approval-mode with terminal availability, so a yolo-default
session (which still blocks on the opening-message prompt when `-m` is absent)
skips the editor gate.

Fix: introduce a terminal-availability seam (`ISystemEnvironment.isatty()`) and a
dedicated `setup_editor` decision DISTINCT from the approval `interactive` flag.
Compute it at the CLI boundary (where `interactive`, `pipeline`, and `message` are
all known) as:

`setup_editor = system_env.isatty() AND (not pipeline) AND (interactive OR message is None)`

The `isatty()` term keeps CI/piped runs headless; the
`(interactive OR message is None)` term means "the session will actually read the
terminal" (either the approval loop runs, or the opening-message prompt will
fire). Key the editor gate on `if setup_editor:` and pass `setup_editor=False`
from the one-shot `handle_plan_generation`.

Debt folded in-slice (user-aligned): retire the redundant hidden non-interactive
CLI aliases (`--yes` / `--no-interactive` / `--non-interactive`), collapsing
`interactive` to `not (_resolve_yolo(...) or pipeline)`, and document `-y` (or
non-TTY stdin) as the headless/automated path in the CLI contract.

Decision matrix:

| entry point | interactive | `-m` given | pipeline | TTY | setup_editor |
| --- | --- | --- | --- | --- | --- |
| `start` | yes | no | no | yes | yes |
| `start -m "x"` | yes | yes | no | yes | yes |
| `start -y` (yolo_default) | no | no | no | yes | yes (FIX) |
| `start -y -m "x"` | no | yes | no | yes | no |
| `start -p -m "x"` | no | yes | yes | yes | no |
| any run, non-TTY stdin | – | – | – | no | no |
| `plan` (one-shot) | – | – | – | – | no (forced) |

The Shadow-File verification proved the decoupling flips the outcome with all
other inputs held constant (REAL preflight: no prompt; decoupled shadow: prompt
fires, editor persisted).

Test strategy: drive `_run_cli_preflight_check` across the truth table with a
stubbed `discover_editors` plus `typer.prompt` and a TTY toggle on the
`ISystemEnvironment` double; add one end-to-end acceptance test through the CLI
adapter for the yolo-without-`-m` case.

## Deliverables

- [ ] **Contract** - Add `isatty(self) -> bool` to `ISystemEnvironment` (docstring: whether a terminal is attached to stdin; wraps `sys.stdin.isatty()`).
- [ ] **Harness** - In `tests/harness/setup/test_environment.py`, give auto-specced `ISystemEnvironment` doubles a deterministic `isatty()` default and expose a TTY-on/TTY-off toggle for tests.
- [ ] **Seam** - Add a `setup_editor: bool` parameter to `_run_cli_preflight_check`, replacing the editor gate's reliance on `interactive`.
- [ ] **Wiring** - Compute `setup_editor` in `start`/`resume` as `system_env.isatty() and not pipeline and (interactive or message is None)`, thread it through `handle_new_session` / `handle_resume_session`, and pass `setup_editor=False` from `handle_plan_generation`. Bundle the behavioral tests (yolo-without-`-m` on a TTY prompts; `-y -m`, pipeline, and non-TTY skip).
- [ ] **Logic** - Change the editor gate condition in `_run_cli_preflight_check` to `if setup_editor:` and cover the truth table with unit tests.
- [ ] **Migration** - Update `test_preflight_check_gates_editor_validation_on_interactive_flag` (and any test asserting the old coupling) and any `mock_port(ISystemEnvironment)` site that now needs an explicit `isatty` return.
- [ ] **Cleanup (flag consolidation)** - Remove the hidden `--yes` / `--no-interactive` / `--non-interactive` aliases from `start`/`resume`/`execute` in `__main__.py`, collapsing each `interactive` expression to `not (_resolve_yolo(...) or pipeline)` (the `pipeline` term only where defined). Migrate the two raw `--no-interactive` test call sites (`tests/suites/acceptance/test_cli_ux_improvements.py`, `tests/suites/integration/core/services/test_session_resume.py`) to `-y`.
- [ ] **Cleanup (docs)** - Amend `editor-validation-and-discovery.md` §2/§4 to state editor setup is gated on "will the session read the terminal" (not on `--yolo`); document in `docs/architecture/adapters/inbound/cli.md` (referenced from `ARCHITECTURE.md`) that headless/automated runs use `-y` (or non-TTY stdin), not the retired hidden aliases.

## Implementation Notes

(To be filled by the Developer.)

## Verification

1. On a terminal with `yolo_default: true` and `editor: ""`, run `teddy start` -> the "Editor Setup" prompt appears in preflight.
2. Select a numbered editor -> `.teddy/config.yaml` `editor:` updates and existing comments are preserved.
3. Run `teddy start -y -m "x"` on a terminal -> NO editor prompt (fully-specified batch run).
4. Run `teddy start --pipeline -m "x"` -> no editor prompt.
5. With stdin redirected (`teddy start -y < /dev/null`) -> no editor prompt (non-TTY).
6. Run `teddy start -n` / `teddy start -m "x"` on a terminal with `editor: ""` -> the prompt still appears (interactive).
7. Confirm the retired hidden flags (`--yes`, `--no-interactive`, `--non-interactive`) are gone: `teddy start --non-interactive` fails with an unknown-option error.
