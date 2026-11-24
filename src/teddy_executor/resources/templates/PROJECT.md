# Project Dashboard: {{Project Name}}

## Product Vision
The overarching goals, target audience, unique value proposition, and major future directions for the product.

**Format:** 2-3 paragraphs describing the product's mission, target users, and what makes it unique.

## Guiding Principles
Core engineering philosophy, quality standards, and foundational rules that dictate how the team builds software.

**Format:** Bulleted list. Each entry: `N. **Principle Name:** Description and how it applies to daily work.`

## Workflow Standards
Defines the high-level artifact lifecycle and conventions for project management documents.

- **Artifact Lifecycle:** How work flows (e.g., Spec → Milestone → Slice).
- **Archiving Policy:** When and how completed artifacts are archived or deleted.

## Tooling
Project automation is exposed through a thin command runner (`justfile` recommended; see [docs/templates/tooling.md](docs/templates/tooling.md)), with multi-step logic living in `scripts/` (subject to all quality gates) rather than `spikes/` or `tests/`. Agents bind to these exact commands:

| Command | Purpose |
| --- | --- |
| `just test` | Run the full test suite via the project runner |
| `just commit "<type>(<scope>): <desc>"` | Stage all changes, run pre-commit auto-fixers, and commit locally |
| `just push` | Fast rebase and push to remote |
| `just ci-watch` | Monitor remote CI workflows and attribute regressions |
| `just logs <run-id> ["<step>"]` | Extract sanitized CI failure logs |
| `just probe "<reason>"` | Trigger the Remote Probing Protocol for isolated CI diagnostics |

When a repetitive task or multi-step command sequence arises, agents must not run long ad-hoc shell commands. Add a dedicated recipe/script in `scripts/`, wire it through the project runner, and document its usage here.

## Releases
The project release lifecycle:

1. **Triage:** Determine semantic version bump (patch, minor, major) by inspecting conventional commits since the last tag.
2. **Release Notes:** Write notes at `docs/project/releases/v<version>.md` capturing net user-facing outcomes.
3. **Version Bump:** Update the project manifest version field.
4. **Approval Gate:** Present release notes and version bump for user approval.
5. **Commit:** Commit version bump with `chore(release): bump version to <version>`.
6. **Tag:** Create and push annotated tag `git tag -a v<version> -m "v<version>"`.
7. **Publish:** Publish release assets or GitHub Release.

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

<!--
Mandatory Prerequisite: For new projects, Milestone 0 (Project Bootstrapping) must be completed before feature work begins.
Initialize docs/project/milestones/00-project-bootstrapping.md with:
- Runtime Standards: Idiomatic packaging, dependency management, and project boilerplate.
- Project Readme: End-user entry point with overview, prerequisites, and usage.
- Tooling Entry Points: Test runner and standard commands (test, commit, push, ci-watch, logs, probe) via docs/templates/tooling.md.
- Local Quality Gates: Pre-commit auto-fixers and post-commit test gate via docs/templates/pre-commit.md.
- Continuous Integration: Parallel OS matrix test suite and static analysis jobs via docs/templates/ci.md.
-->

A compact index of upcoming and completed milestones. Detailed requirements, guidelines, and slices live in each milestone document (`docs/project/milestones/`).

| Milestone | Status | Goal | Specs |
| --- | --- | --- | --- |
| [Project Bootstrapping](milestones/00-project-bootstrapping.md) | `PLANNED` | Establish runtime, testing, quality gates, CI/CD, and project tooling infrastructure. | — |
