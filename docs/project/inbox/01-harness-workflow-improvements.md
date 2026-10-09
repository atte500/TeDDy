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

- ⬜ Ready to implement (decisions settled)
- 🚫 Dropped / Rejected (kept in context for rationale)

---

## To Do

Ordered by execution priority. Every theme has been evaluated and all strategic decisions are resolved.

### Tier 3 — Strategic Themes (All Decisions Settled & Ready)

---

#### Theme 1: Specifications, Artifact Lifecycles & Planning Artifacts
*Focus: How requirements flow from discovery to delivery without artifact duplication, drift, or maintenance churn.*

- **[S1] Collapse `specs/features/` $\to$ Invariants + Milestone Requirements + Task Briefs (Resolved):** ⬜
  - **Retire ephemeral feature specs:** Eliminate throwaway feature specification documents and drop the `specs/features/` vs `specs/invariants/` subfolder division.
  - **Permanent Invariants (`docs/project/specs/`):** Kept as a flat directory reserved strictly for long-lived system invariants, protocols (e.g. MRP), core data models, and non-negotiable architectural rules. The `specification-document.md` template is dedicated exclusively to these invariants.
  - **Strategic Scope in Milestones:** Pathfinder authors feature goals, requirements, and acceptance criteria directly into `docs/project/milestones/MM-name.md` (summarized in `PROJECT.md`'s Roadmap).
  - **Tactical Execution:** Architect decomposes milestones directly into Vertical Slices (`docs/project/slices/MM-NN-name.md`). Pathfinder drafts Task Briefs (`docs/project/tasks/NN-name.md`) for one-off tactical work.
  - **Prompt & Template Updates:** Update `pathfinder.xml`, `architect.xml`, `PROJECT.md`, and `specification-document.md` to remove all references to feature spec drafting and deletion.
- **[11] Release Process in PROJECT.md Template (Resolved):** ⬜
  - Add a **Release Process** topic under `## Workflow Standards` in the `PROJECT.md` template, documenting how the project handles version tagging (e.g., `git tag vX.Y.Z`), changelogs, packaging, and distribution publishing.
- **[19] Friction Inbox (`docs/project/inbox/`):** 🚫 **Dropped.** No unmanaged inbox directory. Process frictions are resolved immediately by Pathfinder into `PROJECT.md` (`Workflow Standards` / `Guiding Principles`) or triaged in working discussions. Technical debt remains in code or milestone planning.
- **[24] Specification Lifecycles:** ⬜ Closed into **[S1]**.

---

#### Theme 2: Pathfinder Direct-Execution Boundary & Delegation Options
*Focus: Clarifying what Pathfinder executes directly versus what it delegates, and rationalizing available handoff targets.*

- **[S3] Pathfinder Direct-Execution Boundary (Resolved):** ⬜
  - **Non-Behavioral Deliverables (Direct Execution):** Pathfinder directly executes documentation updates, template modifications, project tracking documents (`PROJECT.md`, milestones, tasks, invariant specs), file moves/renames (`git mv`), and static configuration text. In Phase 6 (Conclusion), it emits a terminal summary to the user without delegating.
  - **Behavioral Deliverables (Mandatory Delegation):** Pathfinder is strictly prohibited from writing or modifying production code and test suites.
    - Tactical / small behavioral changes $\to$ Pathfinder creates a **Task Brief** (`docs/project/tasks/NN-name.md`) and hands off directly to the **Developer**.
    - Milestone-level features / structural changes $\to$ Pathfinder updates the **Milestone** and hands off to the **Architect**.
    - High-uncertainty investigations $\to$ Hands off to **Prototyper** or **Debugger**.
- **[17] Drop Assistant from Pathfinder Delegation (Resolved):** ⬜
  - Remove `<handoff target="assistant">` from `pathfinder.xml`.
  - Pathfinder executes doc/file chores directly rather than delegating them to Assistant. Assistant remains an independent entry-point agent for direct user invocation and pipeline (`-p`) runs.
- **[N9] Pathfinder XML Structure Cleanup (Resolved):** ⬜
  - Relocate `<handoff_targets>` cleanly inside `pathfinder.xml` and fix the misplaced closing `</workflow>` tag.

---

#### Theme 3: Assistant Fast Iteration & Pipeline Mode
*Focus: Making the Assistant usable for single-shot commands, scripting, and autonomous pipeline runs.*

- **[S4] Assistant Action-First Execution, Pre-Commit Approval Gate & Pipeline Default (Resolved):** ⬜
  - **Action-First Execution:** Eliminate the Phase 1 pre-execution alignment `## Message` from `assistant.xml`. Assistant starts executing immediately without pre-turn conversational friction.
  - **Pre-Commit Review Gate (Phase 2):** After completing and verifying changes, message the user with a summary of modifications and test results, awaiting explicit user confirmation before committing.
  - **Conclusion & VCP (Phase 3):** Upon explicit user approval, tear down temporary artifacts, commit via VCP (`make commit '<msg>'`), and conclude. Remove the mandatory handoff to Pathfinder.
  - **Pipeline Mode (`-p`) Default:** Make the `assistant` agent the default agent for `teddy run -p` runs in the harness CLI (executing and validating changes up to the review checkpoint).

---

#### Theme 4: Developer Workflow, QA Rigor & Handoff Routing
*Focus: Ensuring the Developer produces clean, fully verified work before completion, and returns control to the proper agent.*

- **[12] Dynamic Terminal Handoff Routing (Resolved):** ⬜
  - When the slice finishes, Developer dynamically routes handoff based on the active Milestone:
    - *Next slice un-designed* (no slice `.md` exists) $\to$ Hand off to **Architect** to design next slice JIT.
    - *Next slice designed* $\to$ Hand off to **Prototyper** (if unresolved unknowns) or **Developer**.
    - *All slices complete in Milestone* $\to$ Hand off to **Pathfinder** to close milestone and review roadmap.
- **[13] Slice Completion Lifecycle Transition (Resolved):** ⬜
  - Developer transitions slice status to `Completed`, marks milestone `[x]`, and commits immediately upon passing the end-user verification gate.
- **[21] Scoped Quality Suppressions & Deliverable-Driven Refactoring (Resolved):** ⬜
  - **Phase 2 Step 3 (Refactor):** Strict file-scoped hygiene. Bare `# noqa` and bare `# type: ignore` are strictly forbidden. Any suppression must be narrowly scoped to a specific rule code (e.g. `# type: ignore[import-untyped]`) with an explanatory comment, and must never be used to mask fixable code flaws.
  - **Phase 5 Step 2 (Consistency Check):** If cross-deliverable logic duplication or structural friction is found across the slice, do not modify code ad-hoc in Delivery; instead, append an explicit `Refactor` or `Cleanup` deliverable to the slice and loop back to Phase 1.
- **[22] Multi-Scenario End-User Verification (Resolved):** ⬜
  - Phase 5 Step 5: Execute slice's `## Verification` checklist across multiple real end-user scenarios via `EXECUTE` (running real entry points / CLI commands with various flags and inspecting real outputs/exit codes).
- **[N8] Developer Dangling Rules Integration (Resolved):** ⬜
  - Integrate Developer Rule 10 (Runtime Contract Assertions) directly into **Phase 2 Step 2 (Green)**.
  - Integrate Developer Rule 11 (Test Layer Isolation & Public Boundary Testing) directly into **Phase 2 Step 1 (Red)**.
  - Remove all trailing `<rule>` tags from `developer.xml`.

---

#### Theme 5: Technical Debt Handling & Architectural Doc Maintenance
*Focus: Eliminating unscheduled debt graveyards, enforcing direct scheduling into Milestones/Slices, and keeping docs synchronized with code.*

- **[10] Eliminate `## Technical Debt` Section & Enforce Actionable Scheduling (Resolved):** ⬜
  - **Eliminate `## Technical Debt` Section:** Completely remove the `## Technical Debt` section from the `PROJECT.md` template and TeDDy's own real `docs/project/PROJECT.md`. No holding pen or junk drawer for unscheduled debt.
  - **Remove "Harvest Debt" Steps Everywhere:** Delete the mandatory `<step name="Harvest Debt">` from all 6 agent prompts (`architect.xml`, `assistant.xml`, `debugger.xml`, `developer.xml`, `pathfinder.xml`, `prototyper.xml`).
  - **Strict 3-Tier Execution:**
    - **Tier 1 (Micro / Quick-Wins, $\le 3$ lines, file-local):** Fix directly in-flight during the active turn.
    - **Tier 2 (Slice-Scoped Refactoring):** Append an atomic `Refactor` or `Cleanup` deliverable to the active Vertical Slice and resolve it within the session.
    - **Tier 3 (Structural / Cross-Cutting):** Present to the user during an alignment gate. With user approval, schedule directly as a Vertical Slice in the active Milestone (`docs/project/milestones/MM-name.md`) or define a new Milestone in `PROJECT.md`'s Roadmap.
- **[35] Continuous Architecture & Component Doc Synchronization (Resolved):** ⬜
  - Reinforce the "As-Built Update" step across Developer, Prototyper, and Architect: update component designs and `ARCHITECTURE.md` boundaries concurrently whenever contracts or signatures change. Surgically delete obsolete descriptions rather than appending conflicting notes.

---

#### Theme 6: Debugger Workflow, Investigation Methodology & Gating
*Focus: Streamlining the investigation phases, improving user alignment efficiency, and integrating orphaned rules.*

- **[14] / [38] Debugger Gate Consolidation & Systemic Audit Ordering (Resolved):** ⬜
  - **Reorder Systemic Audit to Phase 3:** Run the Systemic Audit autonomously immediately after the isolated sandbox fix is proven in Phase 2, before involving the user.
  - **Single Consolidated Alignment Gate (Phase 4):** Merge the two previous user approval gates into one decisive gate. Message the user with the complete synthesis in a single turn:
    - Root Cause Analysis (RCA) and verified MRE evidence.
    - Sandboxed verification results proving the fix in isolation.
    - Systemic Audit findings (grepped occurrences across the codebase and seam impact).
    - Proposed solution plan: direct trivial fix (Phase 6) vs. Vertical Slice for Developer.
  - Eliminates redundant conversational ping-pong turns while keeping the user fully in control of the final solution.
- **[36] Symptom Triggering & MRE Delta Minimization (Resolved):** ⬜
  - Replace confusing "coarse-to-fine" phrasing with the **Minimization / Pruning Principle** in Phase 1 Step 3:
    - **Trigger the Symptom:** If an existing command, test, or CI failure exists, execute it to observe the failure live. If reported verbally or without an existing test, write a targeted probe script in `spikes/debug/` to trigger the symptom.
    - **Prune to Minimal:** Systematically strip away incidental arguments, harness boilerplate, and surrounding dependencies until the absolute minimal, fastest, deterministic script that reliably triggers the failure remains.
    - This minimal MRE script becomes the immutable benchmark used to evaluate the sandbox fix in Phase 2.
- **[15] / [16] UI/UX & Technical Unknowns Boundaries (Resolved):** ⬜
  - **Prototyper Sandbox Independence:** Prototyper never delegates throwaway sandbox issues to Debugger; it resolves them directly using focused sub-prototypes in `spikes/prototypes/`.
  - **Production UI/UX Bug Diagnosis:**
    - For headless state or rendering errors: Debugger inspects rendered tree / DOM snapshots and state machines autonomously.
    - For visual / interactive perception bugs: Debugger creates a standalone interactive script in `spikes/debug/` and asks the user to confirm the visual glitch.
    - If the bug reveals that the interaction model or UI architecture needs fundamentally new design exploration (rather than a surgical defect repair), Debugger documents findings in the Case File and routes to **Prototyper**.
- **[N2] Debugger Dangling Rules Integration & Makefile Probing (Resolved):** ⬜
  - Integrate Debugger Rule 10 (Debug Mode & Branch by Abstraction) directly into **Phase 2 Step 4 (Proactive Instrumentation)**.
  - Integrate Debugger Rule 11 (Remote Probing Protocol) directly into **Phase 1 Step 3 (Diagnostic MRE & Platform Check)**, strictly mandating `make probe '<reason>'` per `docs/templates/makefile.md` and `docs/templates/ci.md`.
  - Remove all trailing `<rule>` tags from `debugger.xml`.

---

#### Theme 7: Unknowns Taxonomy & Prototyping Approaches
*Focus: Standardizing how risks and uncertainties are classified and de-risked.*

- **[28] Formal Unknowns Category & 3-Tier Taxonomy (Resolved):** ⬜
  - Introduce **`[Formal]`** as a first-class unknown tag alongside `[Technical]` and `[Functional]` in `vertical-slice.md`, `prototyper.xml`, and `architect.xml`.
  - **Zero-Code Resolution:** Ambiguities in business rules, policy decisions, domain definitions, and scope boundaries are categorized as `[Formal]` and resolved **immediately by asking the user** in an alignment turn, strictly forbidding speculative coding or prototyping for formal questions.
- **[33] Boundary Classification (Resolved):** ⬜
  - **`[Technical]` (Works-Like):** External dependencies, third-party libraries, APIs, runtime performance, concurrency, data storage feasibility. Resolved via automated assertion probes and benchmarks.
  - **`[Functional]` (Looks-Like):** User-facing ergonomics, CLI flags, terminal rendering, interactive flows, layout aesthetic. Resolved via interactive demo runners with configurable knobs.
- **[39] Works-Like vs. Looks-Like Prototyping Archetypes (Resolved):** ⬜
  - Embed the two distinct archetypes in `prototyper.xml`:
    - For `[Technical]` items $\to$ build assertion-based probes proving system contracts and runtime behavior.
    - For `[Functional]` items $\to$ build interactive scenario runners exposing tunable parameters/knobs for user evaluation.
- **[N10] Prototyper Gate Consolidation (Resolved):** ⬜
  - **Eliminate Phase 1 Triage Gate:** Prototyper proceeds autonomously into Phase 2 (Prototyping) without asking permission to build, *unless* an unresolved `[Formal]` unknown requires user clarification first.
  - **Preserve Phase 3 Showcase Gate:** Retain as the single core interactive checkpoint where the user tests the runner/assertions and provides behavioral feedback.
  - **Eliminate Phase 4 Pre-Commit Gate:** After Showcase approval, Prototyper updates docs, commits via VCP (Phase 5), and emits **one single terminal Message** in Phase 6 summarizing the updated slice/component docs and providing the Developer handoff command.
  - Cuts Prototyper user interruptions from 4 down to 1 high-value gate (plus terminal handoff).

---

#### Theme 8: Git Hooks, CI Quality Gates & Tooling
*Focus: Improving commit safety, quality-failure detection, and foundational tool configs.*

- **[S2] Streamline `make commit` (Eliminate Double Pre-Commit Run & Redundant `no-verify`) (Resolved):** ⬜
  - **Single Execution:** In `docs/templates/makefile.md` (and TeDDy's own real root `Makefile`), update the `commit` recipe so `git commit` is called with `--no-verify`:
    ```makefile
    commit: ARGS := $(filter-out commit,$(MAKECMDGOALS))

    commit:
    	@[ -n "$(ARGS)" ] || { echo "Usage: make commit '<message>'"; exit 1; }
    	git add .
    	-pre-commit run
    	git add .
    	git commit -m "$(ARGS)" --no-verify
    	-git pull --rebase
    	-git push
    ```
  - **Eliminate Double Hook Firing:** Because Make already executes `-pre-commit run` and re-stages auto-formatted files, having Git fire `.git/hooks/pre-commit` a second time was redundant and blocked agents on minor linter warnings.
  - **Drop `no-verify` Command Flag:** Simplify usage across all prompts and docs to standard `make commit '<message>'`. Remove the `no-verify` goal logic.
  - **Unskippable Test Gate Preserved:** `--no-verify` only bypasses the `pre-commit` stage; the `post-commit` test gate (`.githooks/post-commit.py` running `make test`) remains active and unskippable.
  - **Synchronize TeDDy's Real `Makefile`:** Update the real root `Makefile` in this repository to match this streamlined recipe, and update `MRP.xml` Rule 6 accordingly.
- **[37] Omit Destructive Revert Instructions (Resolved):** ⬜
  - Remove all destructive `git reset --hard` sentences from `developer.xml` (Phase 3 Step 4) and `debugger.xml` (Phase 6 Step 5).
  - Test failures trigger diagnostic analysis in Rationale and surgical adjustments (or state transition to OFF-TRACK 🟡), preserving working code and uncommitted context.
- **[31] Milestone 0 `.gitignore` Requirement (Resolved):** ⬜
  - Add an explicit requirement to Milestone 0 in `PROJECT.md` to configure a project-tailored `.gitignore` (ignoring language/OS caches, `.tmp/`, build artifacts, but keeping `spikes/` tracked so prototypes and probes remain version-controlled). No separate template file needed.
- **[N11] Ad-Hoc Slices & Developer Slice Exclusivity (Resolved):** ⬜
  - Preserve ad-hoc slices (`00-NN-name.md`) for non-milestone behavioral changes.
  - Developer operates **exclusively** on Vertical Slices (never raw Task Briefs).
  - Tactical / non-behavioral chores are executed directly by Pathfinder or Assistant.

---

#### Theme 9: Prompt Hygiene, State Dashboard & Harness Consistency
*Focus: Refining response mechanics, eliminating communication loops, and documenting harness internals.*

- **[N1] User Directives & Communication Hygiene in Rule 13 (Resolved):** ⬜
  - In `MRP.xml` Rule 13 (`Communication Hygiene`):
    - Whenever the user sends a message, the agent MUST immediately log any user decisions, constraints, or directives into `WIP & REMINDERS` as `[TODO]` (for tasks) or `[!]` (for constraints).
    - The agent is **strictly forbidden from sending another `## Message`** until all those `[TODO]` items are resolved `[✓]` (or unless the agent transitions to `BLOCKED 🔴`).
    - Agents must never re-ask questions the user has already answered, and must never restate decisions or explanations already delivered in prior messages.
- **[29] URL Read Fallback (`curl` & JS-heavy pages) (Resolved):** ⬜
  - In MRP Rule 5 ("Information Gathering Workflow"):
    - If `READ` on a URL fails or returns empty/unusable shells, fall back to `EXECUTE curl -sL '<url>'`.
    - If the page requires client-side JavaScript rendering, create a minimal diagnostic probe script to inspect the raw data/API.
- **[30] Jargon Elimination & Nuanced Replacements (Resolved):** ⬜
  - Audit all agent prompts to replace non-standard jargon with crisp engineering equivalents:
    - *"Zero-Touch Verification"* $\to$ **"Isolated Sandbox Verification"** (`spikes/debug/shadow_{file}.py`).
    - *"Anti-Mock Poisoning"* $\to$ **"Test Double Integrity (Ban Global Patching)"** (constructor injection + in-memory fakes + strict autospec).
    - *"Zero-Cost Abstractions"* (for Python `assert`) $\to$ **"Runtime Contract Assertions (`assert`)"**.
    - *"Subcutaneous Testing"* $\to$ **"Public Boundary Acceptance Testing"** (outermost entry point without importing internal core models).
    - *"The Tracer Bullet"* $\to$ **"End-to-End Skeleton Wiring"** (wiring components end-to-end with stubbed returns before complex logic).
    - *"Green-to-Green"* $\to$ **"Continuous Green State"** (every deliverable/commit leaves test suite fully passing).
    - *"Controllers"* $\to$ **"Coordinators & Application Services"**.
    - *"Deliverable Dependency Sequence"* $\to$ **"Dependency-Ordered Deliverables"**.
    - *"Contract/Expansion -> Migration -> Cleanup/Contraction"* $\to$ **"Non-Breaking Parallel Change (Expand $\to$ Migrate $\to$ Contract)"**.
- **[S5] Contract-First Design Ownership & Drop TyDD (Resolved):** ⬜
  - Do NOT introduce "Type-Driven Development" (TyDD) or "Gap-Driven Development" (GDD) as separate formal paradigms.
  - Retain the existing, proven workflow: Architect defines conceptual Port contracts and invariants in Component Docs $\to$ Developer drives out concrete typed interfaces and implementations via classic TDD (Red $\to$ Green $\to$ Refactor) $\to$ Mypy verifies static type safety in CI.
- **[S6] Document Assembly Pipeline in `ARCHITECTURE.md` (Resolved):** ⬜
  - Update TeDDy's repository `ARCHITECTURE.md` to document:
    1. The `PromptManager` assembly pipeline: `Agent Name:` injection $\to$ agent XML $\to$ `MRP.xml` append inside `<system>` $\to$ legacy `<response_format>` check.
    2. Overridable user prompts (`resources/config/prompts/*.xml` copied to `.teddy/prompts/`) vs. non-overridable core protocol (`resources/MRP.xml`).
    3. Template generation lifecycle (`teddy init templates` copying `resources/templates/` to `docs/templates/`).

---

### Tier 4 — Final verification (last step)

- **[N6] Full prompt / template / docs sanity check** — After Tiers 1–3 land, audit all 6 agent prompts for inconsistencies: (a) across agents; (b) within each agent's own workflow/phases; and (c) between the new templates/process and the current state of TeDDy's own docs, repo, and setup (e.g. the `MRP.xml` relocation to `src/teddy_executor/resources/` + injection logic, the new real `Makefile` `make test` target, the renamed bundled templates, and the `docs/templates/` self-hosting gap). ⬜ Last step.

---

## Concrete File-by-File Changes Specification

Here is the exact breakdown of every file that will change and the specific modifications required:

---

### 1. Harness Configuration & Core Protocols

#### `src/teddy_executor/resources/MRP.xml`
* **Rule 5 (Information Gathering):** Add URL fallback instruction: if `READ` on a remote URL fails or returns an empty JavaScript shell, fall back to `EXECUTE curl -sL '<url>'`; for client-side JS apps, create a minimal probe script (`[29]`).
* **Rule 6 (Version Control Protocol):** Update `make commit '<msg>'` instructions: drop the `no-verify` CLI argument; explain that `make commit` runs pre-commit checks and commits with `--no-verify` to eliminate double hook execution, while the post-commit test gate remains unskippable (`[S2]`).
* **Rule 13 (Communication Hygiene):** Add User Directives enforcement: instructions and decisions in user messages must be logged as `[TODO]` or `[!]` under `WIP & REMINDERS`. Agents are strictly forbidden from sending another `## Message` until all those `[TODO]` items are marked `[✓]` (or unless entering `BLOCKED 🔴`). Never re-ask answered questions or repeat previous message content unprompted (`[N1]`).

---

### 2. Agent Prompts (`src/teddy_executor/resources/config/prompts/`)

#### `pathfinder.xml`
* **Workflow & Boundary:** Codify direct execution for non-behavioral tasks (docs, templates, project files, renames, chores) with terminal summary in Phase 6 without delegation (`[S3]`).
* **Delegation Targets:** Mandate delegation for behavioral code/tests to Developer (via Milestone or ad-hoc slice `00-NN`) and architecture to Architect. Remove `<handoff target="assistant">` (`[17]`).
* **XML Structure:** Relocate `<handoff_targets>` cleanly and remove the misplaced duplicate closing `</workflow>` tag (`[N9]`).
* **Retire Feature Specs:** Remove references to drafting/deleting ephemeral feature specs; author feature goals/requirements directly into Milestone docs; reserve `docs/project/specs/` for permanent invariants (`[S1]`).

#### `assistant.xml`
* **Phase 1 (Execution):** Action-first execution loop; eliminate the Phase 1 pre-execution alignment `## Message` (`[S4]`).
* **Phase 2 (Review Gate):** Message the user with a concise summary of changes and test results, awaiting explicit user approval to commit (`[S4]`).
* **Phase 3 (Conclusion):** Upon explicit user approval, execute teardown, commit via VCP (`make commit '<msg>'`), and conclude. Remove the mandatory "return to Pathfinder" instruction (`[S4]`).

#### `architect.xml`
* **Retire Feature Specs:** Stop referencing `specs/features/`; cross-reference `PROJECT.md` Roadmap and author `docs/project/milestones/MM-name.md` directly (`[S1]`).
* **Conceptual Contracts:** Clarify that Architect defines conceptual Port responsibilities, operations, and invariants in Component Docs, leaving concrete typing and implementation to Developer (`[S5]`).
* **Jargon Replacements (`[30]`):**
  * Phase 2 Step 1: Replace "Controllers over flat delegation" with *"Coordinators and Application Services over leaky direct delegation"*.
  * Phase 3 Step 9: Replace "Deliverable Dependency Sequence" with *"Dependency-Ordered Deliverables"*.
  * Phase 3 Step 9: Replace "Contract/Expansion -> Migration -> Cleanup/Contraction" with *"Non-Breaking Parallel Change (Expand $\to$ Migrate $\to$ Contract)"*.
* **Technical Debt:** Align debt handling with the 3-Tier Debt Policy (`[10]`).

#### `prototyper.xml`
* **Gate Consolidation (`[N10]`):**
  * Eliminate Phase 1 Step 4 Triage Gate: proceed autonomously into prototyping unless blocked by an unresolved `[Formal]` unknown.
  * Retain Phase 3 Showcase Gate as the single core interactive checkpoint.
  * Eliminate Phase 4 Step 11 pre-commit gate: update docs, commit via VCP, and emit one terminal Message in Phase 6 with Developer handoff.
* **Unknowns Taxonomy:** Embed `[Formal]` (ask user directly), `[Technical]` (works-like assertion probe), and `[Functional]` (looks-like interactive runner with knobs) (`[28]`, `[33]`, `[39]`).
* **Sandbox Independence:** Explicitly state that Prototyper resolves prototype bugs via sub-prototypes in `spikes/prototypes/` and never delegates sandbox code to Debugger (`[15]`).

#### `debugger.xml`
* **Workflow Re-ordering & Gate Consolidation (`[14]`, `[38]`):**
  * Move Systemic Audit to Phase 3 (runs autonomously immediately after Shadow File proof).
  * Collapse Phase 3 and Phase 5 gates into a single comprehensive Alignment Gate in Phase 4 (presenting RCA + MRE + Shadow proof + Systemic audit + solution proposal).
* **MRE Pruning Principle:** Update Phase 1 Step 3 to use the delta minimization/pruning methodology instead of "coarse-to-fine" (`[36]`).
* **Integrate Dangling Rules (`[N2]`):**
  * Fold Rule 10 (Debug Mode & Branch by Abstraction) into Phase 2 Step 4 (Proactive Instrumentation).
  * Fold Rule 11 (Remote Probing Protocol) into Phase 1 Step 3 (Diagnostic MRE & Platform Check), calling `make probe '<reason>'`.
  * Delete trailing `<rule>` tags.
* **Omit Destructive Revert:** In Phase 6 Step 5, delete `revert all changes via git reset --hard` on test failure (`[37]`).
* **Jargon Replacement:** Replace "Zero-Touch Verification" with *"Isolated Sandbox Verification"* (`[30]`).
* **UI/UX Bugs:** Clarify headless tree/snapshot checks vs interactive repro commands for user confirmation (`[16]`).

#### `developer.xml`
* **Slice Exclusivity:** Clarify Developer operates exclusively on Vertical Slices (milestone `MM-NN` or ad-hoc `00-NN`) (`[N11]`).
* **Integrate Dangling Rules & Jargon Polish (`[N8]`, `[30]`):**
  * Fold Rule 11 into Phase 2 Step 1 (Red). Replace "Subcutaneous Testing" with *"Public Boundary Acceptance Testing"*, "Anti-Mock Poisoning" with *"Test Double Integrity (Ban Global Patching)"*, and "The Tracer Bullet" with *"End-to-End Skeleton Wiring"*.
  * Fold Rule 10 into Phase 2 Step 2 (Green). Replace "Zero-Cost Abstractions" with *"Runtime Contract Assertions (`assert`)"*.
  * Delete trailing `<rule>` tags.
* **Refactor & Code Hygiene:** In Phase 2 Step 3, strictly ban bare `# noqa` / `# type: ignore`; require narrowly-scoped error codes with reason comments (`[21]`).
* **Consistency Check Refactoring:** In Phase 5 Step 2, if cross-deliverable logic duplication or structural friction is found, append an atomic `Refactor` or `Cleanup` deliverable to the slice and loop back to Phase 1 (`[21]`).
* **Omit Destructive Revert:** In Phase 3 Step 4, delete `Abort: EXECUTE git reset --hard HEAD && git clean -fd` (`[37]`).
* **Verification, Completion & Dynamic Handoff:**
  * Phase 5 Step 5: Multi-scenario end-user smoke testing via `EXECUTE` (`[22]`).
  * Transition slice status to `Completed` and milestone item `[x]` upon passing verification (`[13]`).
  * Dynamically route terminal handoff: Architect (next slice un-designed), Prototyper/Dev (next slice ready), Pathfinder (milestone finished) (`[12]`).

---

### 3. Templates (`src/teddy_executor/resources/templates/`)

#### `PROJECT.md` (Template)
* **Spec Organization:** Remove `specs/features/` vs `specs/invariants/` split. All specs under `docs/project/specs/` are permanent invariants (`[S1]`).
* **Numbering Standard:** Document `MM-NN-name.md` for milestone slices, `00-NN-name.md` for Milestone 0 (bootstrapping) and ad-hoc slices outside milestones (`[N11]`).
* **Milestone 0 Requirements:** Add explicit `.gitignore` setup requirement (keeping `spikes/` tracked) (`[31]`).
* **Release Process:** Add release process guidelines under `## Workflow Standards` (version tagging, changelogs, publication) (`[11]`).
* **Technical Debt Section:** Completely delete the `## Technical Debt` section and its logging hygiene rules (`[10]`).

#### `specification-document.md`
* Update description and instructions to reflect that this template is strictly for **permanent system invariants**, protocols, domain rules, and non-negotiable architectural laws (`[S1]`).

#### `vertical-slice.md`
* Update `## Key Unknowns` section to define the 3-tier taxonomy: `[Formal]` (ask user directly), `[Technical]` (works-like), and `[Functional]` (looks-like) (`[28]`, `[33]`).

#### `makefile.md`
* Update `commit` recipe to include `--no-verify` in `git commit`. Remove the `no-verify` argument filter and document the single-execution rationale (`[S2]`).

#### `ARCHITECTURE.md` (Template)
* Update Conventions & Standards to reflect streamlined `make commit` (no `no-verify` flag), Test Double Integrity, Runtime Contract Assertions, and Continuous Green State (`[30]`).

---

### 4. Repository Tooling & Harness Code

#### `Makefile` (TeDDy's Real Root Makefile)
* Update `commit` recipe to include `--no-verify` in `git commit` and drop `no-verify` goal filtering to match `makefile.md` (`[S2]`).

#### `ARCHITECTURE.md` (TeDDy's Own Architecture Document)
* Document the `PromptManager` assembly flow (`Agent Name:` injection, `MRP.xml` append inside `<system>`, legacy `<response_format>` check), prompt override mechanisms, and template init flow (`[S6]`).

#### `src/teddy_executor/cli/commands/run.py` (Harness CLI)
* Update default agent for pipeline mode (`-p` / `--pipeline`) to `assistant` (`[S4]`).

#### `docs/project/PROJECT.md` (TeDDy's Real Repo Dashboard)
* Completely remove the `## Technical Debt` section to match the updated template standards (`[10]`). Make sure all items are planned in Roadmap instead.

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
- **Generalized Makefile provisioning into `MRP.xml` rule 12** — Consolidated inline Makefile creation sentences into rule 12 ("Template-First Documentation & Tooling").
- **Full-suite run commands abstracted to `make test`** — full-suite run instructions now invoke `make test`.
- **`MRP.xml` rule 12 covers `ci.md` + `pre-commit.md`** — directs agents to follow templates for CI and pre-commit setup.

### Init & Templates
- **[8] Vertical slice scope slug** capped at 2 kebab-case words in `vertical-slice.md`.
- **[20] PROJECT.md template** gained a `## Templates` table (all 10 bundled templates + purposes).
- **[23] PROJECT.md template** gained **Run Environment** + **Build & Run Commands** standards.
- **[N4] Slice 03-03 Done/To-Do** — slice 03-03 gained a "Progress (Done vs To Do)" section.
- **Template filename reconciliation** — bundled files renamed to the artifact-type convention (`milestone.md`, `vertical-slice.md`, `case-file.md`, `task-brief.md`); stale counts fixed; `ci.md` added.

### Communication & Workflow Hygiene
- **[9]/[25]/[26]/[34] → `MRP.xml` rule 13 (Communication Hygiene)** — no repeated titles, no repeated Message content, `[!]` findings in dashboard, TL;DR line on every Message.
- **[27] Optional line ranges** removed from the `READ` action.
- **[32] `--no-verify` cleanup** — `MRP.xml` VCP rule 6 post-conditions mandate follow-up cleanup commit after a bypass.

### Pre-commit Setup
- **[18] Concise pre-commit quick-start** added to `ARCHITECTURE.md` template.
- **[N7] `pre-commit.md` template** — bundled template documenting Pre-commit framework setup and post-commit test gate.

### Tier 1 — Mechanical Content
- **[N5] Per-doc-type file-numbering conventions** — `PROJECT.md` template Workflow Standards enumerates filename conventions for each artifact type.
- **[N3] CI-history extraction → `make logs`** — CI-log extraction abstracted into `make logs <run-id> '<step-name>'` in `makefile.md` template and real Makefile.
