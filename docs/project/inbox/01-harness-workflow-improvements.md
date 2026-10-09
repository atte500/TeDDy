# Harness & Workflow Improvements — Open Discussion Backlog

- **Status:** Active (working backlog)
- **Owner:** Pathfinder
- **Last Updated:** 2026-10-09

## Purpose

Single source of truth for improvement ideas raised during the harness/prompt review. The document is split into two clean halves so status is never ambiguous:

- **To Do** — the actionable backlog, ordered by execution priority (each entry notes its blocker/dependency).
- **Done** — a compact record of completed work, kept only for traceability so later sessions do not re-litigate settled points.

Bracketed numbers refer to the original 40-item list; `Nx` marks new items raised during review; `Sx` marks strategic items raised during the 2026-10-09 prompt/workflow review. A theme appears under **To Do** only while it still has open work; fully completed themes live only under **Done**.

## Status Legend

- ⬜ Not started / ready to start
- ❓ Needs a strategic decision before implementation

---

## To Do

Ordered by execution priority. Items within a tier are independent; every item names any dependency it has. `❓` needs a decision before implementation; `⬜` is ready to start.

### Tier 3 — Strategic (requires joint decisions)

- **[10]** Handle technical debt directly instead of dumping it in `PROJECT.md`; larger items → existing/new milestone (align with the user before any roadmap update).
- **[12]** Developer hands back to **Pathfinder** (not Architect) when done.
- **[13]** Developer marks the slice **Completed** before handing to the user for verification.
- **[14]** Debugger: systemic audit **before** proposing the solution; ideally a single alignment gate.
- **[15]** Debugger invokes **Prototyper** first when technical unknowns persist (or create a Task Brief like Pathfinder — should Architect too?).
- **[16]** Prototyper isolates UI/UX bugs in a smaller focused prototype, or Debugger steps in; Debugger needs an effective user-facing bug diagnosis method.
- **[17]** Pathfinder: drop Assistant from delegation options; implement tactical work directly.
- **[19]** Consider `docs/project/inbox/` for process frictions that are not technical debt (this file is the first entry).
- **[21]** Developer: proactive QA phase (handle debt, remove linter suppressions, unify duplicate logic).
- **[22]** Developer: run a real manual smoke test as an end-user before handoff.
- **[24]** Distinguish invariants (long-lived) vs feature specs (short-lived, folded in if needed); define lifecycles.
- **[28]** Add a **Formal Unknown** category (clearable by asking the user), alongside Technical/Functional unknowns. ⬜ (new concept)
- **[29]** Use `CURL` when `READ` on a URL fails; create a spike for JS-heavy pages. ⬜ (new behavior)
- **[30]** Review for workflow streamlining; avoid unofficial jargon. ⬜ (strategic)
- **[31]** `.gitignore` template + instruction to use it. ⬜ (InitService already embeds a `.gitignore` default for `.teddy/`)
- **[33]** External-facing (libs/APIs) → Technical Unknown; user-facing → Functional Unknown. ⬜
- **[35]** Update component/architectural docs when code changes; fill gaps; remove redundancy (keep information where most relevant).
- **[36]** Coarse-to-fine spike methodology: build a minimal spike, add fidelity until the bug reproduces; phases reproduce → isolate → solve.
- **[37]** Relax "revert on test failure" (do not auto-revert); audit Developer for a similar rule.
- **[38]** Reduce to a single alignment gate after root cause + MRE + Shadow Fix.
- **[39]** Prototyper: "looks-like" vs "works-like" prototypes (maps to functional vs technical unknowns).
- **[N1] Track answered user questions in the State Dashboard** — Log, under WIP & REMINDERS, which user questions/requests have already been answered, so agents do not repeat resolved points or re-ask answered questions. ❓ Decide exact marker/wording.
- **[N2] Debugger "dangling" rules** — The two Debugger-specific rules (`Debug Mode & Branch by Abstraction`, `Remote Probing Protocol`) currently sit orphaned inside `<workflow>` after the final phase. Integrate them into the workflow phases and/or move protocol detail into templates. ⬜
- **[S1] Collapse `specs/features/` → invariants + Milestone Requirements + Task Briefs.** Retire feature specs: strategic *what/why* lives in **Milestone Requirements**; tactical *how* lives in **Task Briefs**; reserve the Specification Document template for **long-lived invariants**. Caveat: reconcile the "Specification Document" references in the Pathfinder and Architect prompts. (Refines **[24]**.) ❓
- **[S2] Autonomous CI / quality-failure detection & autofix.** Keep the local post-commit test gate **blocking**; add an **agent-facing detection command** (e.g. a `make ci` target) plus a **"CI Preflight"** instruction so agents fix a red build/quality verdict *before* proceeding; surface the non-blocking quality result through the same command. Caveat: a post-commit hook **cannot** synchronously report on remote CI. Sub-question: keep the local `git reset --soft HEAD~1` revert, or switch to report-only? (Refines **[37]**.) ❓
- **[S3] Pathfinder direct-execution boundary.** Codify an **Execution Boundary** with no mid-workflow branch: execute directly when the deliverable is **non-behavioral** (docs, templates, config text, artifact creation, file moves/renames); delegate **production logic/tests/runtime → Developer** and **design/contracts → Architect**. The only conditional is the **terminal handoff**. (Refines **[17]**.) ❓
- **[S4] Assistant: remove pre-execution alignment; default `-p` to Assistant.** Strip the Assistant's Phase-1 alignment Message so it emits **ONE terminal Message**, then make **pipeline (`-p`) runs default to the Assistant**. Caveat: `-p` exits after the **first** `## Message`, so *any* message-first agent (including the `pathfinder` default) is unusable in `-p`. ❓
- **[S5] Type-driven / gap-driven development ownership.** Make the already-implicit **Contract-First Design + Mypy + Design-by-Contract + Prototyper→Developer** flow *explicit* (typed contracts as the Architect's first artifact; the Developer may stub the typed signature to drive the Red phase) **without new jargon or a new phase**. ❓
- **[S6] Document prompt assembly & bundling in `ARCHITECTURE.md`.** Document (a) the `PromptManager` assembly pipeline — `Agent Name:` injection, `MRP.xml` append inside `<system>`, and the legacy `<response_format>` detection; (b) the bundled/overridable prompt set (`resources/config/prompts/*.xml` copied to `.teddy/prompts/`) versus the **non-overridable** `resources/MRP.xml`; and (c) the `resources/templates/` → `docs/templates/` init flow. ⬜ (documentation task)

### Tier 4 — Final verification (last step)

- **[N6] Full prompt / template / docs sanity check** — After Tiers 1–3 land, audit all 6 agent prompts for inconsistencies: (a) across agents; (b) within each agent's own workflow/phases; and (c) between the new templates/process and the current state of TeDDy's own docs, repo, and setup (e.g. the `MRP.xml` relocation to `src/teddy_executor/resources/` + injection logic, the new real `Makefile` `make test` target, the renamed bundled templates, and the `docs/templates/` self-hosting gap). ⬜ Last step.

---

## Done (for traceability)

Completed 2026-10-08 and 2026-10-09. Kept compact — full detail lives in Git history and the linked slices.

### Tier 2 — Harness Code
- **[1] MRP as a separate injected layer** — `PromptManager.fetch_system_prompt()` injects the `Agent Name:` line, appends `MRP.xml` after the agent-specific XML (inside `<system>`), runs the legacy `<response_format>` detection, and fails fast (`FileNotFoundError`) when `MRP.xml` is missing — plus tests. Slice **03-02**.
- **[7] `teddy init templates`** — The command ships and regenerates `docs/templates/` from the bundled defaults; bare `teddy init` no longer creates `docs/templates/` on first run. Slice **03-03**.
- **[6] Prompt divergence check** — `teddy start` warns when local prompts differ from bundled defaults and instructs `teddy init prompts`.

### Prompt Architecture & MRP
- **[2] Whitespace normalization** across the prompt XMLs.
- **[Agent Name] injection (design)** — the `Agent Name:` line is the first line of the assembled prompt; the MRP `- **Agent:**` metadata resolves from it (slice 03-02).
- **Strip common rules from agent XMLs** — shared `<general_rules>` + `<response_format>` removed from all six agents; Debugger/Developer agent-specific rules relocated into their workflows.
- **MRP.xml creation + relocation** — the base prompt was created and then moved OUT of `resources/config/prompts/` to `src/teddy_executor/resources/MRP.xml`, so it is never grouped with the user-overridable agent prompts; documented in slice 03-02 + milestone 03.

### Makefile & Tooling
- **[3] VCP + probing protocol moved into the Makefile** — the prompts reference `docs/templates/makefile.md` (`MRP.xml` rule 6; Debugger RPP rule 11), with no residual inline VCP shell blocks.
- **[4] `make test`** — target added to the real `Makefile` (`.PHONY: commit probe test`; recipe `uv run pytest`) and documented in the `makefile.md` template.
- **[5] Templates reference the Makefile** — `PROJECT.md` (Milestone 0 + Workflow Standards) and `ARCHITECTURE.md` (Conventions + Makefile Commands).
- **[40] Milestone 0 uses `make test`** — bootstrapping exposes the suite via `make test` and runs it in the post-commit hook.
- **Generalized Makefile provisioning into `MRP.xml` rule 12** — The scattered inline "if a `Makefile` does not exist in the project root, create one following `docs/templates/makefile.md`" sentences (`MRP.xml` rule 6 VCP; Debugger Phase 1 Step 2 and RPP rule 11) were consolidated into a single shared rule 12 ("Template-First Documentation & Tooling"), which also covers the case where a `Makefile` exists but lacks the required target (e.g. `commit`, `probe`, `logs`, `test`).
- **Distinction retained:** TeDDy's own `Makefile` (this repo) vs the `makefile.md` template that instructs *other* projects to create their own.
- **Full-suite run commands abstracted to `make test`** — the "run the full test suite" instructions (`MRP.xml` rule 10; Debugger Phase 6 Step 5; Developer's verification step) now invoke `make test` instead of a raw runner command.
- **`MRP.xml` rule 12 covers `ci.md` + `pre-commit.md`** — rule 12 ("Template-First Documentation & Tooling") now also directs agents to follow `docs/templates/ci.md` for CI workflows and `docs/templates/pre-commit.md` for pre-commit setup.

### Init & Templates
- **[8] Vertical slice scope slug** capped at 2 kebab-case words in `vertical-slice.md`.
- **[20] PROJECT.md template** gained a `## Templates` table (all 10 bundled templates + purposes).
- **[23] PROJECT.md template** gained **Run Environment** + **Build & Run Commands** standards.
- **[N4] Slice 03-03 Done/To-Do** — slice 03-03 gained a "Progress (Done vs To Do)" section (blueprints removed; bundled templates created).
- **Template filename reconciliation** — bundled files renamed to the artifact-type convention (`milestone.md`, `vertical-slice.md`, `case-file.md`, `task-brief.md`); stale "9 → 10 files" count fixed; the missing `ci.md` added.

### Communication & Workflow Hygiene
- **[9]/[25]/[26]/[34] → `MRP.xml` rule 13 (Communication Hygiene)** — no repeated titles (or transition to BLOCKED), no repeated Message content, `[!]` findings in the dashboard, and a TL;DR line on every Message.
- **[27] Optional line ranges** removed from the `READ` action.
- **[32] `--no-verify` cleanup** — `MRP.xml` VCP rule 6 post-conditions now mandate a follow-up cleanup commit after a bypass.

### Pre-commit Setup
- **[18] Concise pre-commit quick-start** added to the `ARCHITECTURE.md` template (`pre-commit install`, post-commit hook install, `pre-commit run --all-files`).
- **[N7] `pre-commit.md` template** — Added a bundled `pre-commit.md` template documenting the Pre-commit framework setup (the `.pre-commit-config.yaml` structure, the `pre-commit` + `post-commit` stages, and the unskippable post-commit test gate), modelled on the repo's real `.pre-commit-config.yaml` and `.githooks/post-commit.py`. Referenced from `MRP.xml` rule 12 and listed in the `PROJECT.md` template's Templates table.

### Tier 1 — Mechanical Content
- **[N5] Per-doc-type file-numbering conventions** — The `PROJECT.md` template's Workflow Standards "Numbering" topic now enumerates the filename convention for each artifact type (vertical slices `MM-NN-name.md`, milestones `MM-name.md`, case files `NN-name.md`, task briefs `NN-name.md`, ad-hoc work `00-NN-name.md`).
- **[N3] CI-history extraction → `make logs`** — The Debugger's inline `gh run view ... | awk ...` CI-log extraction was abstracted into a `make logs <run-id> '<step-name>'` target in the `makefile.md` template; the Debugger's Phase 1 Step 2 now references it, and the target is mirrored in TeDDy's real `Makefile`.

---
