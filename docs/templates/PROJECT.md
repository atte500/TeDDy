# Project: {{project_name}}

## Product Vision
The overarching goals, target audience, unique value proposition, and major future directions for the product.

**Format:** 2-3 paragraphs describing the product's mission, target users, and what makes it unique.

## Guiding Principles
Core engineering philosophy, quality standards, and foundational rules that dictate how the team builds software.

**Format:** Bulleted list. Each entry: `N. **Principle Name:** Description and how it applies to daily work.`

## Workflow Standards
Defines the high-level artifact lifecycle and conventions for project management documents.

**Format:** Bulleted list. Each entry defines a specific standard.

### Required Topics:
- **Artifact Lifecycle:** How work flows (e.g., Spec → Milestone → Slice).
- **Numbering:** Artifacts are numbered sequentially using a per-type filename convention so agents can infer the correct filename:
    - **Vertical Slices:** `MM-NN-name.md` (in `docs/project/slices/`) — `MM` is the target Milestone number and `NN` is the sequence number within that milestone.
    - **Milestones:** `MM-name.md` (in `docs/project/milestones/`).
    - **Case Files (Debugger):** `NN-name.md` — numbered sequentially.
    - **Task Briefs:** `NN-name.md` (in `docs/project/tasks/`) — numbered sequentially.
    - **Milestone 0 (bootstrapping) & Ad-hoc work (not tied to a milestone):** `00-NN-name.md` — `00` is used as the Milestone prefix for Milestone 0 bootstrapping slices and for ad-hoc slices. Ad-hoc slices are NOT tracked in Milestone documents or the Roadmap.
- **Archiving Policy:** When and how completed artifacts are archived or deleted.
- **Spec Organization:** Specification documents live in a single flat directory `docs/project/specs/` and are reserved strictly for **permanent system invariants** — formats, contracts, protocols (e.g. the MRP), core data models, and non-negotiable architectural rules. Feature goals, requirements, and acceptance criteria belong in Milestone documents (`docs/project/milestones/`), not in specs. There is no ephemeral `specs/features/` lifecycle.
- **Run Environment:** Specify the project's designated environment/dependency manager (e.g., `uv`, `poetry`, `pip`) and prefix ALL execution commands with its runner (e.g., `uv run pytest`). The chosen runner MUST be reflected in the `Makefile`.
- **Build & Run Commands:** Document the standard commands in the project `Makefile` (see [docs/templates/makefile.md](docs/templates/makefile.md)). At minimum: `make test` (full suite), `make commit '<msg>'` (VCP), and `make probe '<reason>'` (Remote Probing Protocol).
- **Release Process:** Document how releases are cut. At minimum: (1) **Triage** the scope (patch/minor/major) from conventional commits since the last tag; (2) write **release notes** to `docs/project/releases/v<version>.md`; (3) bump the `version` field in the project manifest; (4) present the notes and version bump at an **approval gate**; (5) **commit** (`chore(release): bump version to <version>`) and **tag** (`git tag -a v<version>`); and (6) **publish** (e.g. create a GitHub Release). Adapt the concrete commands to the project's packaging and distribution channel.

## Templates

Before creating or modifying any documentation artifact, agents MUST read the corresponding template from `docs/templates/`. The bundled templates are:

| Template | Purpose |
| -------- | ------- |
| `specification-document.md` | Specification documents (permanent system invariants) |
| `milestone.md` | Milestone documents |
| `vertical-slice.md` | Vertical slice definitions |
| `component-design.md` | Component design documents (ports and contracts) |
| `task-brief.md` | Tactical task briefs |
| `case-file.md` | Debugger case files |
| `PROJECT.md` | This project dashboard |
| `ARCHITECTURE.md` | System architecture document |
| `makefile.md` | Makefile (VCP commit + Remote Probing Protocol commands) |
| `ci.md` | CI workflow template (debug workflow for the Remote Probing Protocol) |
| `pre-commit.md` | Pre-commit framework setup (pre-commit + post-commit test gate) |

These files live in `docs/templates/` and are created or refreshed by `teddy init templates`.

## Roadmap

**Mandatory Prerequisites:** Milestone 0 (Project Bootstrapping) is a required standard that MUST be completed before any feature work begins. It establishes the foundational infrastructure — testing framework, CI/CD pipeline, pre-commit hooks, post-commit test gate, and Makefile — that all subsequent milestones depend upon. No feature work may proceed until these foundations are in place.

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
- **Core Goal:** Establish the foundational project infrastructure for testing, CI/CD, and pre-commit quality gates.
- **Specs:** N/A — Milestone 0 is self-defining.
- **Requirements:**
    - **Testing Framework Setup:** Configure the project's designated test runner (e.g., `pytest`) with test discovery conventions, exposed via a `make test` target (see the Makefile below).
    - **CI/CD Pipeline:** Set up two parallel jobs: 1) Blocking OS matrix test suite with coverage targets. 2) Non-blocking quality checks (formatters, linters, security scanners).
    - **Pre-commit Hooks:** Install the Pre-commit framework with hooks for formatters, linters, security scanners.
    - **Post-commit Hook:** Implement a hook that runs the full test suite via `make test` and reverts the commit on failure (via `git reset --soft HEAD~1`, keeping changes staged). This is the unskippable safety net — `--no-verify` MUST NOT bypass it.
    - **Debug Workflow:** Create `.github/workflows/debug.yml` following [docs/templates/ci.md](docs/templates/ci.md) to enable the Remote Probing Protocol.
    - **Makefile:** Create a `Makefile` following [docs/templates/makefile.md](docs/templates/makefile.md) with `make commit`, `make probe`, and `make test` commands. `make commit` implements the VCP workflow, `make probe` implements the Debugger's Remote Probing Protocol, and `make test` runs the full suite on demand.
    - **`.gitignore` Configuration:** Configure a project-tailored `.gitignore` covering language/OS cache files, build artifacts, virtual environments, and the transient `.tmp/` directory. The `spikes/` directory MUST remain tracked so prototypes and probes stay version-controlled.
