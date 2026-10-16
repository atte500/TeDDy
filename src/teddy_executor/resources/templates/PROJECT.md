# Project Dashboard: {{project_name}}

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
    - **Milestone 0 (bootstrapping) & Ad-hoc work (not tied to a milestone):** `00-NN-name.md` — `00` is used as the Milestone prefix for Milestone 0 bootstrapping slices and for ad-hoc slices. Ad-hoc slices are NOT tracked in Milestone documents or the Roadmap.
- **Archiving Policy:** When and how completed artifacts are archived or deleted.
- **Spec Organization:** Specification documents live in a single flat directory `docs/project/specs/` and are reserved strictly for **permanent system invariants** — formats, contracts, protocols (e.g. the MRP), core data models, and non-negotiable architectural rules. Feature goals, requirements, and acceptance criteria belong in Milestone documents (`docs/project/milestones/`), not in specs.
- **Build & Run Commands:** Document the standard commands in the project `Makefile` (see [docs/templates/makefile.md](docs/templates/makefile.md)). At minimum: `make test` (full suite), `make commit '<msg>'`, `make push`, `make ci-watch` (CI monitoring), and `make probe '<reason>'` (Remote Probing Protocol).
- **Release Process:** Document how releases are cut. At minimum: (1) **Triage** the scope (patch/minor/major) from conventional commits since the last tag; (2) write **release notes** to `docs/project/releases/v<version>.md`; (3) bump the `version` field in the project manifest; (4) present the notes and version bump at an **approval gate**; (5) **commit** (`chore(release): bump version to <version>`) and **tag** (`git tag -a v<version>`); and (6) **publish** (e.g. create a GitHub Release). Adapt the concrete commands to the project's packaging and distribution channel.

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
    - **Language & Runtime Standards:** Set up packaging, dependency management, and project boilerplate using current idiomatic standards for the target language and runtime.
    - **Project Readme:** Create a minimal `README.md` focused strictly on the end-user entry point: product overview, prerequisites, and installation/usage instructions.
    - **Testing & Tooling Entry Points:** Configure the test runner (`pytest`) exposed via `make test`, along with standard `Makefile` targets (`make commit`, `make push`, `make ci-watch`, `make probe`). Configure project `.gitignore` keeping `spikes/` tracked.
    - **Local Quality Gates:** Install Pre-commit with fast local hooks (formatters, secret detection, merge conflict checks) and the unskippable post-commit test gate (`.githooks/post-commit.py`) that runs `make test` and reverts on failure.
    - **CI/CD & Remote Diagnostics:** Set up parallel GitHub Actions jobs: 1) Blocking OS matrix test suite. 2) Non-blocking quality checks. Configure `.github/workflows/debug.yml` for the Remote Probing Protocol.
