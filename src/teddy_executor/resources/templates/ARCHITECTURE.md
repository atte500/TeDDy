# System Architecture: {{Project Name}}

## Conventions & Standards

This section defines foundational engineering practices. Each entry MUST be a specific, enforceable rule.

**Template format:** `- **Rule Name:** Description and enforcement mechanism.`

### Recommended: customize per project
- **Version Control:** Branch strategy and commit conventions. Every commit MUST pass the full test suite before and after each change (`make test`). Commit locally per deliverable; defer the push to the session Conclusion and report CI results back (blocking only on failures the push introduced).
- **Run Environment:** Designated runner (e.g., `uv run`, `poetry run`).
- **Failure Transparency:** Error handling policy — specific exceptions only, no silent suppression.
- **Testing Strategy:** Define test types (Unit, Integration, Acceptance), boundaries, and filesystem hygiene. Mandate **Test Double Integrity**. Ban global patching. Use in-memory fakes for state-managing outbound ports. Use strictly autospec-bound mocks only for external side-effects.
- **Runtime Contract Assertions:** Enforce Design-by-Contract with native `assert condition, "message"` for pre/post-conditions and invariants (strippable via `python -O`); never custom exceptions for contract checks.
- **Dependency Injection:** Constructor injection mandate; forbid Service Locator and global containers.
- **Centralized Configuration:** Config file location, prohibition of magic numbers.
- **Continuous Integration & Remote Diagnostics:** Parallel CI jobs: 1) Blocking OS matrix test suite. 2) Non-blocking (`continue-on-error: true`) quality checks running fast formatters, linters, security scanners, type checkers, and repository-wide structural checks. Platform-specific and CI-only issues are investigated via the Remote Probing Protocol (`make probe REASON="<reason>"`). See [docs/templates/ci.md](docs/templates/ci.md).
- **Local Quality Gates (Pre-commit & Post-commit):** Local pre-commit hooks MUST stay fast, checking only staged files (formatters, secret detection, merge conflict markers). Heavy, false-positive-prone checks run non-blocking in CI. The full test suite runs via the post-commit hook (`.githooks/post-commit.py`) as an unskippable safety net, reverting automatically on failure. See [docs/templates/pre-commit.md](docs/templates/pre-commit.md).
- **Diagnostic Instrumentation:** High-value diagnostics MUST use zero-cost language-native dead-code elimination (e.g. `if __debug__:`) and Composition Root toggles; mid-logic environment checks are forbidden.
- **Experimental Code:** The `spikes/` directory is reserved for rapid, isolated experimentation (`debug/`, `prototypes/`, `showcases/`) and is explicitly excluded from all quality gates (linters, type checkers, test suites).
- **Directory Conventions:**
  `docs/architecture/BOUNDARY/LAYER/TYPE/name.md` -> Source path: `src/{pkg}/BOUNDARY/LAYER/TYPE/name.ext` -> Test path: `tests/suites/TEST_TYPE/BOUNDARY/LAYER/TYPE/test_name.ext`
- **Makefile Commands:** The `Makefile` is the canonical entry point for the version control workflow and on-demand test runs: `make test` (full suite), `make commit MSG="<msg>"` (local commit with advisory auto-fix and unskippable post-commit test gate), `make push` (rebase and push), `make ci-watch` (CI monitoring), and `make probe REASON="<reason>"` (Remote Probing Protocol). See [docs/templates/makefile.md](docs/templates/makefile.md).

## Ubiquitous Language

The canonical domain vocabulary. All documentation, component names, tests, and agent prompts must use these terms consistently.

**Template format:** `- **Term:** Concise definition and operational boundary.`

- **TermName:** Definition of the core domain concept and its operational boundaries.

## Component & Boundary Map

Single source of truth for system structure, organized by architectural layer.

### Hexagonal Core
Domain entities, value objects, ports, and orchestrating services.

| Component         | Description                     | Contract                                     |
| ----------------- | ------------------------------- | -------------------------------------------- |
| **ComponentName** | One-line responsibility summary | [Link to design doc](./path/to/component.md) |

### Inbound Adapters (Driving)
Entry points initiating calls into the core (CLI, Web UI, API controllers, message consumers).

| Component         | Description                     | Contract                                     |
| ----------------- | ------------------------------- | -------------------------------------------- |
| **ComponentName** | One-line responsibility summary | [Link to design doc](./path/to/component.md) |

### Outbound Adapters (Driven)
Infrastructure implementations fulfilling outbound port contracts (file system, database, external APIs, shell).

| Component         | Description                     | Contract                                     |
| ----------------- | ------------------------------- | -------------------------------------------- |
| **ComponentName** | One-line responsibility summary | [Link to design doc](./path/to/component.md) |

### Test Harness
Test drivers, observers, shared fakes, and test setup fixtures.

| Component         | Description                     | Contract                                     |
| ----------------- | ------------------------------- | -------------------------------------------- |
| **ComponentName** | One-line responsibility summary | [Link to design doc](./path/to/component.md) |

Each Contract column links to the Component Design Document or Interface definition.

## Key Architectural Decisions

A living "System Law" document capturing explicit, prescriptive design decisions.

**Template format:** `- **Subject:** Strict Rule. (Rationale.)`

### Rules for this section:
- Each entry MUST be a single enforceable rule with a brief rationale.
- Add new entries as decisions are made; never remove without deprecation notice.
- Note exceptions explicitly with their rationale.
