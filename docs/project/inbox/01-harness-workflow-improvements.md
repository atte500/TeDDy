# Harness & Workflow Improvements — Open Discussion Backlog

- **Status:** Active (working backlog)
- **Owner:** Pathfinder
- **Last Updated:** 2026-10-08

## Purpose

Single source of truth for improvement ideas raised during the harness/prompt review that are **not yet tackled**, so later sessions can pick up context without re-litigating settled points. Completed work is recorded briefly for traceability; active items carry a status marker and, where relevant, the open decision blocking them. Bracketed numbers refer to the original 40-item list; `Nx` marks new items raised during review.

## Status Legend

- ✅ Done
- 🟡 Partially done (design/content complete; follow-up outstanding)
- ⬜ Not started
- ❓ Open strategic decision required (needs user alignment before implementation)

---

## A. Prompt Architecture & MRP — 🟡 content done, ⬜ harness

- **[1] MRP as a separate injected layer** — ✅ Design/content done: `MRP.xml` created (shared general rules + response format), injected **after** the agent-specific XML, inside `<system>`. Legacy check: skip MRP when a resolved prompt already contains `<response_format>`. ✅ **Relocated** `MRP.xml` OUT of `resources/config/prompts/` to `src/teddy_executor/resources/MRP.xml` (2026-10-08) so it is never grouped with the user-overridable agent prompts; documented in slice 03-02 + milestone 03. ⬜ Harness: `PromptManager.fetch_system_prompt()` must implement injection + legacy detection + fail-fast + tests (slice 03-02 To Do).
- **[2] Whitespace normalization across prompt XMLs** — ✅ Done.
- **[Agent Name] Inject `Agent Name:` line** — ✅ Design captured (slice 03-02): first line of the assembled prompt; MRP metadata `- **Agent:**` resolves from it.
- **Strip common rules from agent XMLs** — ✅ Done: shared `<general_rules>` + `<response_format>` removed from all six agents; Debugger/Developer agent-specific rules relocated into their workflows.

## New Items (raised during review)

- **[N1] Track answered user questions in the State Dashboard** — Log, under WIP & REMINDERS, which user questions/requests have already been answered, so agents do not repeat resolved points or re-ask answered questions. ❓ Decide exact marker/wording. ⬜ Not started.
- **[N2] Debugger "dangling" rules** — The two Debugger-specific rules (`Debug Mode & Branch by Abstraction`, `Remote Probing Protocol`) currently sit orphaned inside `<workflow>` after the final phase. ⬜ Integrate properly into the workflow phases and/or move protocol detail into templates.
- **[N3] CI-history extraction → Makefile** — The long `gh run view ... | awk ...` CI-log extraction in the Debugger's Reproduction step should be abstracted into the Makefile template (e.g. a `make logs` target). ⬜ Not started.
- **[N4] Templates slice Done-vs-To-Do** — Slice 03-03 needs a Done/To-Do section noting blueprints were already moved to templates. ✅ Done: slice 03-03 gained a "Progress (Done vs To Do)" section (blueprints removed; bundled templates created). Bundled template filenames were also reconciled to the artifact-type convention (`milestone.md`, `vertical-slice.md`, `case-file.md`, `task-brief.md`) across all doc sites.
- **[N5] Document per-doc-type file-numbering conventions in the PROJECT.md template** — The `PROJECT.md` template's Workflow Standards "Numbering" topic is currently a generic one-liner ("Sequential MM-NN format, 00 prefix for ad-hoc work"). Expand it to enumerate the file-naming convention for EACH documentation artifact type, making the prefix mapping explicit (e.g. vertical slices `MM-NN-name.md`; milestones `MM-name.md`; case files `NN-name.md`; task briefs `NN-task-brief.md`; ad-hoc work `00-NN-name.md`), so agents can infer the correct filename per artifact. ⬜ Not started. (Raised 2026-10-08.)
- **[N6] Full prompt / template / docs sanity check (final step)** — As the LAST step of the harness overhaul, audit all 6 agent prompts for inconsistencies: (a) across agents; (b) within each agent's own workflow/phases; and (c) between the new templates/process and the current state of TeDDy's own docs, repo, and setup (e.g. the `MRP.xml` relocation to `src/teddy_executor/resources/`, the new real `Makefile` `make test` target, the renamed bundled templates, and the `docs/templates/` self-hosting gap). ⬜ Not started. (Raised 2026-10-08.)

## B. Makefile & Tooling Consolidation — ✅ done

- **[3] Move VCP + probing protocol into the Makefile**; reference `docs/templates/` files instead of blueprints. ✅ Done: the Makefile + `docs/templates/makefile.md` template exist, and the prompts reference them (`MRP.xml` rule 6 references `docs/templates/makefile.md`; Debugger RPP rule 11 references `make probe` + the template) with no residual inline VCP shell blocks.
- **[4] `make test`** — Add to the template and the real Makefile; adjust prompts; the VCP should instruct agents to create the command if missing. ✅ Done: `test:` target added to the real `Makefile` (`.PHONY: commit probe test`; recipe `uv run pytest`) and documented in the `makefile.md` template (Test usage + Test Workflow sections); the template instructs agents to add the target if missing.
- **[5] Templates reference the Makefile** — `PROJECT.md` and `ARCHITECTURE.md` templates should reference the Makefile and `make` commands where relevant. ✅ Done: `PROJECT.md` (Milestone 0 + Workflow Standards) and `ARCHITECTURE.md` (Conventions + Makefile Commands) reference the Makefile and its `make test` / `make commit` / `make probe` commands.
- **[40] Milestone 0 uses `make test`** — Bootstrapping sets up `make test` and uses it in the post-commit hook. ✅ Done: the `PROJECT.md` template's Milestone 0 requires a testing framework exposed via `make test` and a post-commit hook that runs the suite via `make test`.
- **Key distinction:** TeDDy's own `Makefile` (this repo) vs the `makefile.md` **template** that instructs *other* projects to create their own. Both must be clearly described.

## C. Init & Templates System — 🟡 content done, ⬜ harness

- **[6] Prompt divergence check** — `teddy start` should warn when local prompts differ from bundled defaults and instruct `teddy init prompts`. ⬜ Deferred (production code).
- **[7] `teddy init templates`** — Implement; instruct agents to use it when `docs/templates/` is missing. ⬜ Deferred (production code — slice 03-03).
- **[8] Vertical slice scope slug** — Cap at 2 words in the template. ✅ Done: `vertical-slice.md` `Scope Slug` line now carries a 1-2 kebab-case word directive.
- **[20] PROJECT.md template** — Add a section linking templates with descriptions. ✅ Done: `PROJECT.md` template gained a `## Templates` table (all 10 bundled templates + purposes).
- **[23] PROJECT.md template** — Specify the environment manager (e.g. `uv`, poetry). ✅ Done: `PROJECT.md` template Workflow Standards gained a **Run Environment** entry (designated env/dependency manager; runner reflected in the Makefile) and a **Build & Run Commands** entry.

## D. Agent Handoff Chain & Workflow — ❓ strategic

- **[12]** Developer hands back to **Pathfinder** (not Architect) when done.
- **[13]** Developer marks the slice **Completed** before handing to the user for verification.
- **[14]** Debugger: systemic audit **before** proposing the solution; ideally a single alignment gate.
- **[15]** Debugger invokes **Prototyper** first when technical unknowns persist (or create a Task Brief like Pathfinder — should Architect too?).
- **[16]** Prototyper isolates UI/UX bugs in a smaller focused prototype, or Debugger steps in; Debugger needs an effective user-facing bug diagnosis method.
- **[17]** Pathfinder: drop Assistant from delegation options; implement tactical work directly.
- **[21]** Developer: proactive QA phase (handle debt, remove linter suppressions, unify duplicate logic).
- **[22]** Developer: run a real manual smoke test as an end-user before handoff.
- **[39]** Prototyper: "looks-like" vs "works-like" prototypes (maps to functional vs technical unknowns).

## E. Documentation & Debt Management — ❓ strategic

- **[10]** Handle technical debt directly instead of dumping in `PROJECT.md`; larger items → existing/new milestone (align with the user before any roadmap update).
- **[19]** Consider `docs/project/inbox/` for process frictions that are not technical debt (this file is the first entry).
- **[24]** Distinguish invariants (long-lived) vs feature specs (short-lived, folded in if needed); define lifecycles.
- **[35]** Update component/architectural docs when code changes; fill gaps; remove redundancy (keep information where most relevant).

## F. Communication & Workflow Hygiene — 🟡 content done, ⬜ remaining

- **[9]** Avoid repeating titles across turns; on vicious loops → enter BLOCKED 🔴. ✅ Done: encoded as `MRP.xml` general rule 13 (Communication Hygiene).
- **[25]** Do not repeat prior Message content; do not send a new Message until previously agreed work is done (except BLOCKED). ✅ Done: encoded as `MRP.xml` rule 13. *(overlaps N1)*
- **[26]** Log important findings as `[!]` in the dashboard. ✅ Done: encoded as `MRP.xml` rule 13.
- **[27]** Remove optional line ranges from `READ`. ✅ Done.
- **[28]** Add a **Formal Unknown** category (clearable by asking the user), alongside Technical/Functional unknowns. ⬜ Deferred (new concept).
- **[29]** Use `CURL` when `READ` on a URL fails; create a spike for JS-heavy pages. ⬜ Deferred (new behavior).
- **[30]** Review for workflow streamlining; avoid unofficial jargon. ⬜ Deferred (strategic).
- **[31]** `.gitignore` template + instruction to use it. ⬜ Deferred (InitService already embeds a `.gitignore` default for `.teddy/`).
- **[32]** Linter workflow: commit with `--no-verify`, then a cleanup commit before resuming. ✅ Done: `MRP.xml` VCP rule 6 post-conditions now mandate a follow-up cleanup commit after a `--no-verify` bypass.
- **[33]** External-facing (libs/APIs) → Technical Unknown; user-facing → Functional Unknown. ⬜ Deferred.
- **[34]** Add a TL;DR line at the end of every Message. ✅ Done: encoded as `MRP.xml` rule 13.

## G. Debugger Methodology — ❓ strategic

- **[36]** Coarse-to-fine spike methodology: build a minimal spike, add fidelity until the bug reproduces; phases reproduce → isolate → solve.
- **[37]** Relax "revert on test failure" (do not auto-revert); audit Developer for a similar rule.
- **[38]** Reduce to a single alignment gate after root cause + MRE + Shadow Fix.

## H. Pre-commit Setup — ✅ done

- **[18]** Add the concise pre-commit quick-start reference. ✅ Done: `ARCHITECTURE.md` template gained a **Pre-commit Quick-Start** section (`pre-commit install`, post-commit hook install, `pre-commit run --all-files`).

---

## Suggested Ordering

Authoritative execution order for the whole backlog. Every group (**A–H**) and every New Item (**N1–N6**) is placed below so nothing falls through the cracks.

1. **Mechanical, well-understood & low-risk — content items** — **B** (Makefile & tooling), **C** content (Init & Templates), **F** (communication/workflow hygiene), **H** (pre-commit setup). Concrete, low-ambiguity changes needing no strategic debate. ✅ **Content items done** (2026-10-08): B ([3]/[4]/[5]/[40]), C content ([8]/[20]/[23]), F ([9]/[25]/[26]/[32]/[34]), H ([18]) — plus the `MRP.xml` relocation, the template-filename reconciliation, and **[N4]** (slice 03-03 Done/To-Do section).
2. **Remaining mechanical content follow-ups (low-risk)** — **[N5]** document the per-doc-type file-numbering convention in the `PROJECT.md` template; **[N3]** extract the Debugger's CI-log command (`gh run view ... | awk ...`) into the `makefile.md` template (e.g. a `make logs` target). Both are content-only edits to templates/prompts. ⬜ Next.
3. **Developer work — A harness** — slices **03-02** (agent-name injection + `importlib.resources` MRP append + legacy detection + fail-fast + tests) and **03-03** (`teddy init templates` + InitService + blueprint directives). Unblocks the already-stripped agent XMLs; on the critical path. Includes the deferred **C** harness items **[6]/[7]**. ⬜ Ready — nothing blocking; hand to the Developer.
4. **Strategic — requires joint decisions** — **D** (handoff chain & workflow), **E** (documentation & debt management), **G** (debugger methodology), plus **[N1]** (track answered user questions) and **[N2]** (Debugger "dangling" rules), and the deferred **F** items ([28]/[29]/[30]/[31]/[33]). These need careful tradeoff analysis before implementation — mostly prompt/workflow restructures that land after the harness code. ❓ Alignment required.
5. **Final verification — last step** — **[N6]** full sanity check of all 6 agent prompts across agents, within each agent's workflow/phases, and between the new templates/process and the current repo/docs/setup. Run only after steps 1–4 land. ⬜ Last.
