# Slice: Type-Safe Vulture Whitelisting
- **Status:** Planned
- **Milestone:** [09-architectural-debt-reconciliation](../milestones/09-architectural-debt-reconciliation.md)
- **Component Docs:** [docs/architecture/tests/harness/vulture_whitelist.md](../architecture/tests/harness/vulture_whitelist.md)

## Business Goal
Replace the brittle, string-based `ignore_names` list in `pyproject.toml` with a type-safe whitelist module to improve the reliability of dead-code detection and reduce maintenance friction.

## Scenarios

### Scenario 1: Whitelist Generation & Integration
> As a Developer, I want Vulture to ignore my Textual handlers and abstract port methods via a Python whitelist so that I don't have to update the global TOML file.
```gherkin
Given a file "tests/harness/vulture_whitelist.py" simulating usage of "on_mount" and "IUserInteractor"
When I remove "on_mount" and "IUserInteractor" from "pyproject.toml" ignore_names
And I add "tests/harness/vulture_whitelist.py" to Vulture's paths
Then "vulture" MUST NOT report these as unused
And "mypy" MUST pass for the whitelist file
```

## Deliverables
- [ ] **Contract** - Create `tests/harness/vulture_whitelist.py` with initial usage simulations.
- [ ] **Configuration** - Add `tests/harness/vulture_whitelist.py` to `tool.vulture.paths` in `pyproject.toml`.
- [ ] **Cleanup** - Remove all method names from `tool.vulture.ignore_names` in `pyproject.toml`.
- [ ] **Cleanup** - Remove all type/class names from `tool.vulture.ignore_names` in `pyproject.toml`.
- [ ] **Cleanup** - Verify all quality gates (`vulture`, `mypy`, `ruff`) pass.
