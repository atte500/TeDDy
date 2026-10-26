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
The project `Makefile` is the canonical automation interface. Build targets are decomposed into modular fragments under `make/*.mk` (see [docs/templates/makefile.md](docs/templates/makefile.md)). Standard targets include `make test` (full test suite execution via the project runner), `make commit MSG="<type>(<scope>): <desc>"` (run pre-commit hooks, stage auto-fixes, and commit), `make push` (fast rebase and push to remote), `make ci-watch` (remote CI workflow monitoring and regression attribution), `make probe REASON="<reason>"` (Remote Probing Protocol for isolated CI diagnostics), and `make logs RUN=<id> [STEP="<name>"]` (extract sanitized CI failure logs).

When a repetitive task or multi-step command sequence arises, agents must not run long ad-hoc shell commands. Add a dedicated target to the appropriate `make/*.mk` fragment and document its usage and flags in this section.

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
| `makefile.md`               | Makefile (commit + Remote Probing Protocol commands)                  |
| `ci.md`                     | CI workflow template (debug workflow for the Remote Probing Protocol) |
| `pre-commit.md`             | Pre-commit framework setup (pre-commit + post-commit test gate)       |

These files live in `docs/templates/` and are created or refreshed by `teddy init templates`.

## Roadmap

**Mandatory Prerequisites:** Milestone 0 (Project Bootstrapping) is a required standard that MUST be completed before any feature work begins. It establishes the foundational infrastructure — testing framework, CI/CD pipeline, pre-commit hooks, post-commit test gate, and Makefile — that all subsequent milestones depend upon. You must complete these foundations before beginning feature work.

A living list of upcoming Milestones and their high-level features.

**Template format:**

```
### Milestone N: [Name] [STATUS]
- **Core Goal:** [High-level objective]
- **Specs:** [Link to Specification Document(s)]
- **Requirements:
    - Requirement 1
    - Requirement 2
```

### Milestone 0: Project Bootstrapping [PLANNED]
- **Core Goal:** Establish foundational infrastructure for testing, quality gates, and automated delivery.
- **Specs:** N/A — Milestone 0 is self-defining.
- **Requirements:**
    - **Runtime Standards:** Set up packaging, dependency management, and project boilerplate using current idiomatic standards for the target language and runtime.
    - **Project Readme:** Create a minimal `README.md` focused strictly on the end-user entry point: product overview, prerequisites, and installation/usage instructions.
    - **Tooling Entry Points:** Configure the test runner (`pytest`) exposed via `make test`, along with standard `Makefile` targets (`make commit`, `make push`, `make ci-watch`, `make probe`). Configure project `.gitignore` keeping `spikes/` tracked.
    - **Local Quality Gates:** Install Pre-commit with fast local hooks (formatters, secret detection, merge conflict checks) and the unskippable post-commit test gate (`.githooks/post-commit.py`) that runs `make test` and reverts on failure.
    - **Continuous Integration:** Set up parallel GitHub Actions jobs: 1) Blocking OS matrix test suite. 2) Non-blocking quality checks. Configure `.github/workflows/debug.yml` for the Remote Probing Protocol.
