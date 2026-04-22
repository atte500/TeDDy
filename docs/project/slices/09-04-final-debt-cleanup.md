# Slice: Final Debt Cleanup
- **Status:** Planned
- **Milestone:** [09-architectural-debt-reconciliation](../milestones/09-architectural-debt-reconciliation.md)

## Business Goal
Achieve 100% compliance with architectural standards and quality gates by resolving prototype leaks, suppressing framework-specific false positives, and streamlining linting rules.

## Scenarios

### Scenario 1: Decouple Core from Prototypes
> As an Architect, I want core services to be independent of the `prototypes/` directory so that the production build is clean and Mypy can correctly resolve module names.
```gherkin
Given a core service (e.g., PlanningService) importing from "prototypes.slice_00_05_logic"
When I remove these imports
And I ensure the required logic is correctly implemented within the core (or marked as TBD for Milestone 10)
Then "poetry run mypy" MUST NOT report duplicate module errors for "slice_00_05_logic"
```

### Scenario 2: Vulture Whitelist Expansion
> As a Developer, I want Vulture to ignore abstract Port methods and Textual framework handlers so that I only see genuine dead code.
```gherkin
Given Vulture reports false positives for "on_mount", "compose", and abstract port methods
When I add these patterns to the "ignore_names" or "ignore_decorators" in "pyproject.toml"
Then "poetry run vulture" MUST report 0 violations for these patterns
```

### Scenario 3: Ruff Magic Value Rationalization
> As a Maintainer, I want to allow magic values in tests without manual suppression so that the test code remains readable and less cluttered.
```gherkin
Given multiple tests containing "# noqa: PLR2004"
When I configure Ruff to ignore "PLR2004" for the "tests/" directory in "pyproject.toml"
And I remove the manual "# noqa" markers
Then Ruff MUST NOT report magic value violations in tests
```

## Deliverables
- [x] **Refactor** - Remove all imports from `prototypes/` in `src/teddy_executor/core/services/`.
- [x] **Configuration** - Update `[tool.vulture]` in `pyproject.toml` with expanded `ignore_names` for Ports and Textual.
- [x] **Configuration** - Update `[tool.ruff.lint.per-file-ignores]` in `pyproject.toml` to ignore `PLR2004` in `tests/**/*`.
- [x] **Cleanup** - Remove manual `# noqa: PLR2004` markers from test files.
- [x] **Cleanup** - Final verification of all quality gates.

## Implementation Notes
- **Refactor (Prototype Decoupling):** Removed `TEDDY_SHOWCASE` and `TEDDY_SHOWCASE_MOCK_LLM` logic from `PlanningService`, `SessionPlanner`, and `SessionService`. These blocks were redundant as production logic now handles interactive prompts and timestamped sessions. Verified via `mypy` (resolving duplicate module errors) and global `pytest` run.
- **Configuration (Quality Gates):** Rationalized Vulture and Ruff configurations to handle framework false positives (`on_mount`, `compose`, `action_*`) and magic values in tests (`PLR2004`).
- **Cleanup:** Removed manual `# noqa` suppressions from the test suite, favoring centralized configuration in `pyproject.toml`. Verified global test suite (644 pass, 2 skip) and quality gates (Ruff/Vulture/Mypy).
