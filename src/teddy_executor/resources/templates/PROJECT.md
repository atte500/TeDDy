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
- **Numbering:** Sequential MM-NN format, 00 prefix for ad-hoc work.
- **Archiving Policy:** When and how completed artifacts are archived or deleted.
- **Spec Organization:** Organize specification documents by lifecycle into two subfolders: `docs/project/specs/invariants/` (formats, contracts, and workflows of record — long-lived system invariants) and `docs/project/specs/features/` (to-be-implemented initiatives that feed the Spec → Milestone → Slice lifecycle — deleted per the Archiving Policy once implemented).
- **Run Environment:** Specify the project's designated environment/dependency manager (e.g., `uv`, `poetry`, `pip`) and prefix ALL execution commands with its runner (e.g., `uv run pytest`). The chosen runner MUST be reflected in the `Makefile`.
- **Build & Run Commands:** Document the standard commands in the project `Makefile` (see [docs/templates/makefile.md](docs/templates/makefile.md)). At minimum: `make test` (full suite), `make commit '<msg>'` (VCP), and `make probe '<reason>'` (Remote Probing Protocol).

## Templates

Before creating or modifying any documentation artifact, agents MUST read the corresponding template from `docs/templates/`. The bundled templates are:

| Template | Purpose |
| -------- | ------- |
| `specification-document.md` | Specification documents (features and invariants) |
| `milestone.md` | Milestone documents |
| `vertical-slice.md` | Vertical slice definitions |
| `component-design.md` | Component design documents (ports and contracts) |
| `task-brief.md` | Tactical task briefs |
| `case-file.md` | Debugger case files |
| `PROJECT.md` | This project dashboard |
| `ARCHITECTURE.md` | System architecture document |
| `makefile.md` | Makefile (VCP commit + Remote Probing Protocol commands) |
| `ci.md` | CI workflow template (debug workflow for the Remote Probing Protocol) |

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

## Technical Debt
Tracks known technical debt for future cleanup.

**Format:** `- [Description including context and location of the debt item.]`

**Logging Hygiene (MUST):**
- **Never re-log the same debt.** If a debt item recurs across commits, fold the new occurrence into the existing entry — do NOT append a new bullet.
- **Prefer fixing directly over logging.** Only log debt that genuinely cannot be resolved in the moment. Do not log-then-resolve a defect that could be fixed immediately.
- **Never log resolved items.** Do not add "informational" or "completed" entries.

**Deletion Policy:** When a technical debt item is addressed (the underlying issue is resolved in a completed milestone/slice), the entry MUST be deleted from this section. Do not mark it as "completed" or "resolved" — remove it entirely. Git history serves as the permanent record.
