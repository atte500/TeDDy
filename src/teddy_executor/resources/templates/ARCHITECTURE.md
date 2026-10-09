# System Architecture: {{project_name}}

## 1. Conventions & Standards

This section defines foundational engineering practices. Each entry MUST be a specific, enforceable rule.

**Template format:** `- **Rule Name:** Description and enforcement mechanism.`

### Recommended: customize per project
- **Version Control:** Branch strategy and commit conventions. Every commit MUST leave the suite in a **Continuous Green State** — the full test suite passes before and after each change.
- **Run Environment:** Designated runner (e.g., `uv run`, `poetry run`).
- **Failure Transparency:** Error handling policy — specific exceptions only, no silent suppression.
- **Testing Strategy:** Test types (Unit/Integration/Acceptance), boundaries, and filesystem hygiene. Mandate **Test Double Integrity**: ban global patching, use in-memory fakes for state-managing outbound ports, and strictly autospec-bound mocks only for un-fakeable external side-effects.
- **Runtime Contract Assertions:** Enforce Design-by-Contract with native `assert condition, "message"` for pre/post-conditions and invariants (strippable via `python -O`); never custom exceptions for contract checks.
- **Dependency Injection:** Constructor injection mandate; forbid Service Locator and global containers.
- **Centralized Configuration:** Config file location, prohibition of magic numbers.
- **CI Pipeline:** Two parallel jobs — 1) Blocking OS matrix test suite with strict test coverage targets. 2) Non-blocking (continue-on-error: true) quality checks running fast formatters, linters, security/secret scanners, type checkers, and repository-wide structural checks (excluding sandboxes and third-party dependencies).
- **Pre-commit Hooks:** Scope (staged files only), required hooks (formatters, linters, type checkers, security scanners).
- **Post-commit Execution:** Full test suite run on commit, automatic revert on failure.
- **Makefile Commands:** The `Makefile` is the canonical entry point for the VCP commit workflow and on-demand test runs. `make test` runs the full suite, `make commit '<msg>'` performs a VCP commit (it runs the pre-commit hooks once and commits with `--no-verify`, while the post-commit test gate remains unskippable), and `make probe '<reason>'` runs the Remote Probing Protocol. See [docs/templates/makefile.md](docs/templates/makefile.md).

### Pre-commit Quick-Start

```shell
pre-commit install                          # install the pre-commit stage hook
pre-commit install --hook-type post-commit  # install the post-commit test gate
pre-commit run --all-files                  # run all hooks manually against the repo
```

## 2. Component & Boundary Map

Single source of truth for system structure, organized by architectural layer.

**Template format (table):**

| Component         | Description                     | Contract                                     |
| ----------------- | ------------------------------- | -------------------------------------------- |
| **ComponentName** | One-line responsibility summary | [Link to design doc](./path/to/component.md) |

### Required Layers:
- **Hexagonal Core:** Domain models, Ports (inbound/outbound), Services.
- **Primary Adapters:** CLI, web UI, API controllers.
- **Outbound Adapters:** File system, database, external APIs, shell.
- **Test Harness:** Drivers, Observers, Setup fixtures.

Each Contract column links to the Component Design Document or Interface definition.

## 3. Key Architectural Decisions

A living "System Law" document capturing explicit, prescriptive design decisions.

**Template format:** `- **Subject:** Strict Rule. (Rationale.)`

### Rules for this section:
- Each entry MUST be a single enforceable rule with a brief rationale.
- Add new entries as decisions are made; never remove without deprecation notice.
- Note exceptions explicitly with their rationale.
