# Project Dashboard: TeDDy

## Product Vision

TeDDy's mission is to apply the **UNIX philosophy** to AI development and create a **Git-like workflow** to embed the entire AI collaboration process directly into the file system.

- **Markdown Files as Interface:** The interface *is* the file system. AI collaboration lives exclusively in plain Markdown files in the local directory, managed with standard developer tools.
- **Data Ownership:** Local-first operation with no cloud lock-in. Total control over privacy and data. The complete workflow and context history resides on the local machine in a portable, open format.
- **Deterministic Operation:** Stateless and transparent. Context goes in as a file, results come out as a file. Every turn is completely deterministic, auditable, and hackable.
- **Human-Centric Workflow:** Action plans are reviewed and approved interactively before execution. A suite of specialized AI personas (Pathfinder, Architect, Developer, Debugger) tackle distinct phases of the software lifecycle using disciplined, proven workflows.

## Guiding Principles

1.  **Jidoka (Autonomation):** *Stop the line immediately when a defect is found.* We make errors obvious so they can be fixed, rather than masking them. Test-Driven Development (TDD) is our primary implementation of Jidoka, preventing flawed code from ever being integrated.
2.  **Poka-Yoke (Mistake-Proofing):** *Design processes so errors can't be made in the first place.* Contract-First Design is our Poka-Yoke. By defining clear "seams" and contracts between all parts of the system—starting with the user—we mistake-proof the architecture.
3.  **The UNIX Philosophy (Small, Sharp Tools):** *Build small, independent components that do one thing well and compose them to handle complexity.* This principle is the foundation of our architecture and development workflow. Each component is a "small, sharp tool" with a single responsibility, communicating through simple, well-defined contracts (Ports).

## Workflow Standards

This section defines the conventions for our project management artifacts.

- **Artifact Lifecycle:** Work flows from `Spec` -> `Milestone` -> `Slice`.
- **Archiving Policy:** Once a feature slice or milestone is fully implemented and merged, its active planning artifacts can be deleted. The Git history serves as the official, permanent archive.
- **Spec Organization:** Specification documents live in a single flat directory `docs/project/specs/` and are reserved strictly for **permanent system invariants** — formats, protocols (e.g. the MRP), schemas, and architectural boundaries. Feature goals, requirements, and acceptance criteria belong in Milestone documents (`docs/project/milestones/`), not in specs. There is no ephemeral `specs/features/` lifecycle.

## Tooling

The project `Makefile` is the current automation interface (modular fragments under `make/*.mk`) and stays bound until [06-06](slices/06-06-tooling-migration.md) retires it in favour of a `justfile` plus tested `scripts/tooling/` helpers. That migration's install path is measured rather than assumed: `uv tool install rust-just` provides `just` 1.59.0 with no compiler required, and `uvx --from rust-just just <recipe>` runs a single recipe with no install at all. Agents must use these exact bound commands until that slice lands:

| Command | Purpose |
| --- | --- |
| `make test` | Run the full test suite via `pytest` |
| `make commit MSG="<type>(<scope>): <desc>"` | Stage all changes, run pre-commit auto-fixers, and commit locally |
| `make push` | Fast rebase and push to remote |
| `make ci-watch` | Monitor and attribute remote CI runs |
| `make logs RUN=<id> [STEP="<name>"]` | Extract and format failed CI step logs |
| `make probe REASON="<reason>"` | Trigger the Remote Probing Protocol |

When a repetitive task or multi-step command sequence arises, agents must not run long ad-hoc shell commands. Add a dedicated target to the appropriate `make/*.mk` fragment (or `scripts/` helper) and document its usage and flags in this section.

## Releases

The release process follows these steps:
1. **Triage:** Determine the scope (patch, minor, major) by reviewing `git log v<last_tag>..HEAD` for conventional commits.
2. **Release Notes:** Create a new file at `docs/project/releases/v<new_version>.md` summarizing features and fixes from the commit log. Record net user-visible outcomes only. Group related changes under one high-level entry instead of listing commits separately. Omit changes that cancel each other out within the release window.
3. **Version Bump:** Update the `version` field in `pyproject.toml`. Confirm the README badges still match `pyproject.toml` (the Python requirement and the license); the PyPI version badge is dynamic and needs no update.
4. **Approval Gate:** Present the proposed release notes and version bump to the user for review and approval.
5. **Commit:** Stage changes (including `uv.lock` if it was modified by the version bump build) and commit with `chore(release): bump version to <new_version>`.
6. **Tag:** Create a local tag with `git tag -a v<new_version> -m "v<new_version>"` and push it with `git push origin v<new_version>`.
7. **Publish:** Create a GitHub Release using `gh release create v<new_version> --title "v<new_version>" --notes-file docs/project/releases/v<new_version>.md`.

## Templates

Before creating or modifying any documentation artifact, agents MUST read the corresponding template from `docs/templates/`. The bundled templates are:

| Template                    | Purpose                                                               |
| --------------------------- | --------------------------------------------------------------------- |
| `specification-document.md` | Specification documents (permanent system invariants)                 |
| `milestone.md`              | Milestone documents                                                   |
| `vertical-slice.md`         | Vertical slice definitions                                            |
| `component-design.md`       | Component design documents (ports and contracts)                      |
| `case-file.md`              | Debugger case files                                                   |
| `PROJECT.md`                | This project dashboard                                                |
| `ARCHITECTURE.md`           | System architecture document                                          |
| `tooling.md`                | Project tooling (command runner contract, `scripts/`, and probing)    |
| `ci.md`                     | CI workflow template (debug workflow for the Remote Probing Protocol) |
| `pre-commit.md`             | Pre-commit framework setup (pre-commit + post-commit test gate)       |

These files live in `docs/templates/` and are created or refreshed by `teddy init templates`.

## Roadmap

A compact index of upcoming and completed milestones. Detailed requirements, guidelines, and slices live in each milestone document (`docs/project/milestones/`). Rows are ordered by priority (milestone numbers are stable IDs, not execution order); the next milestone is the first planned row with all dependencies completed, and multiple milestones may be in progress concurrently when their boundaries do not overlap.

| Milestone | Status | Depends On | Goal | Specs |
| --- | --- | --- | --- | --- |
| Foundational Refactors _(archived)_ | `COMPLETED` | — | Extract prompt blueprints to templates, centralize MRP, and add editor discovery. | — |
| [TUI & UX Enhancements](milestones/04-tui-ux-enhancements.md) | `IN PROGRESS` | — | Enhance interactive TUI visibility and navigation, add MOVE/DELETE actions, and show waiting feedback. | [interactive-session-workflow](specs/interactive-session-workflow.md) |
| [Quality Gate & Debt Reconciliation](milestones/05-quality-gate-debt-reconciliation.md) | `PLANNED` | — | Drive the blocking gates green, enforce the bypass policy with a hook, split CI static analysis, and prune redundant test cases while the advisory metrics stay advisory. | — |
| [Cross-Cutting Consolidation](milestones/06-cross-cutting-consolidation.md) | `PLANNED` | — | Single-source duplicated literals, helpers, doubles, and the action-type registry, unify the exception hierarchy, and migrate tooling to `justfile` + `scripts/`. | — |
| [Runtime Reliability & Boundary Purity](milestones/07-runtime-reliability.md) | `PLANNED` | — | Make session metadata writes durable, the suite deterministic, the heuristics bounded, the resume state single-sourced, and `core` free of adapter libraries. | — |
