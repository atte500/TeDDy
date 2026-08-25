# System Architecture: {{project_name}}

## 1. Conventions & Standards

This section defines foundational engineering practices. Each entry MUST be a specific, enforceable rule.

**Template format:** `- **Rule Name:** Description and enforcement mechanism.`

### Recommended: customize per project
- **Version Control:** Branch strategy and commit conventions.
- **Run Environment:** Designated runner (e.g., `uv run`, `poetry run`).
- **Failure Transparency:** Error handling policy — specific exceptions only, no silent suppression.
- **Testing Strategy:** Test types (Unit/Integration/Acceptance), boundaries, test doubles policy, mock poisoning prevention, filesystem hygiene.
- **Dependency Injection:** Constructor injection mandate; forbid Service Locator and global containers.
- **Centralized Configuration:** Config file location, prohibition of magic numbers.
- **CI Pipeline:** Two parallel jobs — 1) Blocking OS matrix test suite with strict test coverage targets. 2) Non-blocking (continue-on-error: true) quality checks running fast formatters, linters, security/secret scanners, type checkers, and repository-wide structural checks (excluding sandboxes and third-party dependencies).
- **Pre-commit Hooks:** Scope (staged files only), required hooks (formatters, linters, type checkers, security scanners).
- **Post-commit Execution:** Full test suite run on commit, automatic revert on failure.

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
