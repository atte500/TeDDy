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

### Tier 3 — Strategic Themes (Discussion in Progress)

---

#### Theme 1: Specifications, Artifact Lifecycles & Planning Artifacts
*Focus: How requirements flow from discovery to delivery without artifact duplication, drift, or maintenance churn.*

- **[24] Specification Lifecycles:** Distinguish long-lived invariants vs short-lived feature specs; define unambiguous creation, update, and retirement lifecycles for both.
- **[S1] Collapse `specs/features/` $\to$ Invariants + Milestone Requirements + Task Briefs (Refines [24]):** Retire dedicated feature spec documents. Strategic *what/why* lives in **Milestones**; tactical *how* lives in **Vertical Slices** or **Task Briefs**; reserve the `specification-document.md` template strictly for **long-lived system invariants**. Reconcile all references in Pathfinder and Architect prompts. ❓
- **[19] Friction Inbox (`docs/project/inbox/`):** Establish `docs/project/inbox/` as a destination for capturing raw process frictions, backlog thoughts, and workflow ideas that do not qualify as technical debt. ⬜

---

#### Theme 2: Pathfinder Direct-Execution Boundary & Delegation Options
*Focus: Clarifying what Pathfinder executes directly versus what it delegates, and rationalizing available handoff targets.*

- **[17] Pathfinder Tactical Delegation:** Drop the Assistant from Pathfinder's delegation targets; have Pathfinder implement tactical and non-behavioral tasks directly.
- **[S3] Pathfinder Direct-Execution Boundary (Refines [17]):** Codify an explicit execution boundary without mid-workflow branches:
  - **Execute directly:** Non-behavioral deliverables (documentation, templates, configuration text, roadmap adjustments, file moves/renames, chore edits).
  - **Delegate to Developer:** Production runtime logic, tests, and behavior changes.
  - **Delegate to Architect:** Structural design, seam decomposition, and contract definitions.
  - The only conditional branch is the terminal handoff. ❓

---

#### Theme 3: Assistant Fast Iteration & Pipeline Mode
*Focus: Making the Assistant usable for single-shot commands, scripting, and autonomous pipeline runs.*

- **[S4] Assistant Alignment Elimination & Pipeline Default:**
  - Strip the pre-execution Phase 1 alignment gate from `assistant.xml` so it executes immediately and emits **one terminal Message**.
  - Default the pipeline execution flag (`teddy run -p`) to the Assistant so headless scripted runs do not abort on an early alignment message. ❓

---

#### Theme 4: Developer Workflow, QA Rigor & Handoff Routing
*Focus: Ensuring the Developer produces clean, fully verified work before completion, and returns control to the proper agent.*

- **[12] Developer Terminal Handoff Target:** Change Developer's completion handoff from Architect back to **Pathfinder** (or evaluate when/if Architect is still relevant).
- **[13] Slice Completion Lifecycle:** Developer explicitly transitions the Vertical Slice status to `Completed` before requesting user verification.
- **[21] Proactive QA Phase:** Embed an explicit polish step in the Developer workflow (resolving in-scope debt, removing temporary lint suppressions, unifying duplicate logic introduced during Green phase).
- **[22] Manual Smoke Verification:** Developer executes a real manual smoke test as an end-user (e.g. running CLI commands or interactive verification) before handoff, rather than relying exclusively on unit tests.

---

#### Theme 5: Technical Debt Handling & Architectural Doc Maintenance
*Focus: Preventing `PROJECT.md` from becoming an unmanaged debt dumping ground, and keeping docs synchronized with code.*

- **[10] Direct Technical Debt Remediation:** Handle technical debt directly in-flight where possible instead of blindly logging it into `PROJECT.md`. Structure debt into tiers:
  - Micro/quick-wins ($\le 3$ lines, localized): fix immediately.
  - Slice-scoped: include as `Refactor`/`Cleanup` deliverables in the active slice.
  - Large/structural: align with user before scheduling into existing or new milestones.
- **[35] Architectural & Component Doc Synchronization:** Require agents to update component designs and architecture maps concurrently when code changes occur, removing stale redundancy.

---

#### Theme 6: Debugger Workflow, Investigation Methodology & Gating
*Focus: Streamlining the investigation phases, improving user alignment efficiency, and integrating orphaned rules.*

- **[14] / [38] Debugger Gate Consolidation & Systemic Audit Ordering:**
  - Run the Systemic Audit immediately after verifying the root cause with an MRE and Shadow Fix.
  - Collapse multiple alignment gates into a **single alignment gate** where the user receives the complete analysis (RCA + MRE evidence + Shadow fix + Systemic audit + resolution plan) at once.
- **[15] Debugger Escalation to Prototyper:** Clarify when Debugger should invoke Prototyper when deep technical unknowns persist, or author a Task Brief.
- **[16] UI/UX Bug Diagnosis:** Methodology for Prototyper to isolate UI/UX rendering bugs in a minimal focused sandbox when Debugger needs assistance.
- **[36] Coarse-to-Fine Spike Methodology:** Codify coarse-to-fine probing: start minimal, gradually add fidelity until the bug reproduces, following distinct phases (reproduce $\to$ isolate $\to$ solve).
- **[N2] Integrate Dangling Debugger Rules:** Integrate the two orphaned rules at the end of `debugger.xml` (`Debug Mode & Branch by Abstraction` and `Remote Probing Protocol`) directly into their respective workflow phases and templates. ⬜

---

#### Theme 7: Unknowns Taxonomy & Prototyping Approaches
*Focus: Standardizing how risks and uncertainties are classified and de-risked.*

- **[28] Formal Unknowns Category:** Introduce `[Formal]` as a first-class unknown tag (ambiguities in business rules, definitions, or requirements cleared directly by asking the user), alongside `[Technical]` and `[Functional]`. ⬜
- **[33] Boundary Classification:** Explicitly define the boundary: external libraries/APIs/runtime $\to$ `[Technical]`; user-facing UX/interaction $\to$ `[Functional]`. ⬜
- **[39] Looks-Like vs. Works-Like Prototyping:** Map prototyping deliverables to unknown types: "looks-like" for functional/UX unknowns, "works-like" for technical/feasibility unknowns.

---

#### Theme 8: Git Hooks, CI Quality Gates & Tooling
*Focus: Improving commit safety, quality-failure detection, and foundational tool configs.*

- **[37] Relax "Revert on Test Failure":** Evaluate the local post-commit hook's automatic `git reset --soft HEAD~1` behavior; prevent confusion when commit attempts fail tests.
- **[S2] Autonomous CI / Quality-Failure Preflight (Refines [37]):**
  - Add an agent-facing preflight command (e.g. `make ci` or `make check`) running both tests and quality checks.
  - Instruct agents to run this preflight before committing so failures are caught and fixed prior to invoking git commit.
  - Decide whether to keep the post-commit soft-revert as an unskippable backstop or switch to a reporting-only failure gate. ❓
- **[31] `.gitignore` Template:** Provide a standard bundled `.gitignore` template covering `.tmp/`, `spikes/`, and environment caches, with instructions for agents to reference it during bootstrapping. ⬜

---

#### Theme 9: Prompt Hygiene, State Dashboard & Harness Consistency
*Focus: Refining response mechanics, eliminating communication loops, and documenting harness internals.*

- **[N1] State Dashboard Answer Tracking:** Define an explicit marker in `WIP & REMINDERS` (e.g. `[A]`) to record user answers to questions, preventing agents from re-asking answered questions across turns. ❓
- **[29] URL Read Fallback (`curl` / JS-heavy pages):** Instruct agents to fall back to `EXECUTE curl -sL <url>` if `READ` on a remote URL fails, and create a spike for dynamic JS pages. ⬜
- **[30] Prompt Language & Jargon Review:** Audit all agent prompts to streamline instructions and eliminate unofficial or confusing jargon. ⬜
- **[S5] Contract-First Design Ownership:** Clarify typed protocol/contract generation (Architect generates types/contracts $\to$ Developer stubs them to drive Red phase) without inventing new phase names. ❓
- **[S6] Document Assembly Pipeline in `ARCHITECTURE.md`:** Document the `PromptManager` assembly flow (`Agent Name:` injection, `MRP.xml` appending, non-overridable vs overridable assets, and template initialization) in `ARCHITECTURE.md`. ⬜

---

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
