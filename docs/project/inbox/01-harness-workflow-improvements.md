# Harness & Workflow Improvements — Open Discussion Backlog

- **Status:** Active (working backlog)
- **Owner:** Pathfinder
- **Last Updated:** 2026-10-08

## Purpose

Single source of truth for improvement ideas raised during the harness/prompt review. The document is split into two clean halves so status is never ambiguous:

- **To Do** — the actionable backlog, ordered by execution priority (each entry notes its blocker/dependency).
- **Done** — a compact record of completed work, kept only for traceability so later sessions do not re-litigate settled points.

Bracketed numbers refer to the original 40-item list; `Nx` marks new items raised during review. A theme appears under **To Do** only while it still has open work; fully completed themes live only under **Done**.

## Status Legend

- ⬜ Not started
- 🟡 Partially done (design/content complete; harness follow-up outstanding)
- ❓ Needs a strategic decision before implementation

---

## To Do

Ordered by execution priority. Items within a tier are independent.

### Tier 1 — Remaining mechanical content (low-risk, content-only)

- **[N5] Per-doc-type file-numbering conventions in the `PROJECT.md` template** — The template's Workflow Standards "Numbering" topic is a generic one-liner today ("Sequential MM-NN format, 00 prefix for ad-hoc work"). Expand it to enumerate the filename convention for EACH artifact type — vertical slices `MM-NN-name.md`, milestones `MM-name.md`, case files `NN-name.md`, task briefs `NN-task-brief.md`, ad-hoc work `00-NN-name.md` — so agents can infer the correct filename per artifact. ⬜ Not started.
- **[N3] CI-history extraction → Makefile** — Abstract the long `gh run view ... | awk ...` CI-log extraction from the Debugger's Reproduction step into the `makefile.md` template (e.g. a `make logs` target). ⬜ Not started.

### Tier 2 — Harness code (production; on the critical path)

- **[1] MRP as a separate injected layer (harness)** — Design/content is complete (see Done). Remaining: `PromptManager.fetch_system_prompt()` must inject the `Agent Name:` line, append `MRP.xml` after the agent-specific XML (inside `<system>`), run the legacy `<response_format>` detection, and fail-fast (`FileNotFoundError`) when MRP.xml is missing — plus tests. Slice **03-02**. 🟡
- **[7] `teddy init templates`** — Implement the command; instruct agents to use it when `docs/templates/` is missing. Bare `teddy init` and `teddy start`/`teddy resume` also (non-destructively) create `docs/templates/`. Slice **03-03**. ⬜ Deferred (production code).
- **[6] Prompt divergence check** — `teddy start` should warn when local prompts differ from bundled defaults and instruct `teddy init prompts`. ⬜ Deferred (production code).

### Tier 3 — Strategic (requires joint decisions)

**D. Agent Handoff Chain & Workflow**
- **[12]** Developer hands back to **Pathfinder** (not Architect) when done.
- **[13]** Developer marks the slice **Completed** before handing to the user for verification.
- **[14]** Debugger: systemic audit **before** proposing the solution; ideally a single alignment gate.
- **[15]** Debugger invokes **Prototyper** first when technical unknowns persist (or create a Task Brief like Pathfinder — should Architect too?).
- **[16]** Prototyper isolates UI/UX bugs in a smaller focused prototype, or Debugger steps in; Debugger needs an effective user-facing bug diagnosis method.
- **[17]** Pathfinder: drop Assistant from delegation options; implement tactical work directly.
- **[21]** Developer: proactive QA phase (handle debt, remove linter suppressions, unify duplicate logic).
- **[22]** Developer: run a real manual smoke test as an end-user before handoff.
- **[39]** Prototyper: "looks-like" vs "works-like" prototypes (maps to functional vs technical unknowns).

**E. Documentation & Debt Management**
- **[10]** Handle technical debt directly instead of dumping in `PROJECT.md`; larger items → existing/new milestone (align with the user before any roadmap update).
- **[19]** Consider `docs/project/inbox/` for process frictions that are not technical debt (this file is the first entry).
- **[24]** Distinguish invariants (long-lived) vs feature specs (short-lived, folded in if needed); define lifecycles.
- **[35]** Update component/architectural docs when code changes; fill gaps; remove redundancy (keep information where most relevant).

**G. Debugger Methodology**
- **[36]** Coarse-to-fine spike methodology: build a minimal spike, add fidelity until the bug reproduces; phases reproduce → isolate → solve.
- **[37]** Relax "revert on test failure" (do not auto-revert); audit Developer for a similar rule.
- **[38]** Reduce to a single alignment gate after root cause + MRE + Shadow Fix.

**F. Communication & Workflow Hygiene (remaining)**
- **[28]** Add a **Formal Unknown** category (clearable by asking the user), alongside Technical/Functional unknowns. ⬜ Deferred (new concept).
- **[29]** Use `CURL` when `READ` on a URL fails; create a spike for JS-heavy pages. ⬜ Deferred (new behavior).
- **[30]** Review for workflow streamlining; avoid unofficial jargon. ⬜ Deferred (strategic).
- **[31]** `.gitignore` template + instruction to use it. ⬜ Deferred (InitService already embeds a `.gitignore` default for `.teddy/`).
- **[33]** External-facing (libs/APIs) → Technical Unknown; user-facing → Functional Unknown. ⬜ Deferred.

**New Items**
- **[N1] Track answered user questions in the State Dashboard** — Log, under WIP & REMINDERS, which user questions/requests have already been answered, so agents do not repeat resolved points or re-ask answered questions. ❓ Decide exact marker/wording.
- **[N2] Debugger "dangling" rules** — The two Debugger-specific rules (`Debug Mode & Branch by Abstraction`, `Remote Probing Protocol`) currently sit orphaned inside `<workflow>` after the final phase. Integrate them into the workflow phases and/or move protocol detail into templates. ⬜

### Tier 4 — Final verification (last step)

- **[N6] Full prompt / template / docs sanity check** — After Tiers 1–3 land, audit all 6 agent prompts for inconsistencies: (a) across agents; (b) within each agent's own workflow/phases; and (c) between the new templates/process and the current state of TeDDy's own docs, repo, and setup (e.g. the `MRP.xml` relocation to `src/teddy_executor/resources/`, the new real `Makefile` `make test` target, the renamed bundled templates, and the `docs/templates/` self-hosting gap). ⬜ Last step.

---

## Done (for traceability)

Completed 2026-10-08. Kept compact — full detail lives in Git history and the linked slices.

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
- **Distinction retained:** TeDDy's own `Makefile` (this repo) vs the `makefile.md` template that instructs *other* projects to create their own.

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

---
