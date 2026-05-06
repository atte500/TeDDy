# Task: Retire Vulture & Pivot to Coverage-Driven Hygiene

## Status
- **Status:** Planned
- **Priority:** High
- **Type:** Chore / Technical Debt

## Objective
Remove Vulture and its associated manual "bs" (whitelists and generic name masking) and replace it with a "Behavioral Proof of Life" strategy driven by strict test coverage.

## Context
Vulture produces high false positives in Hexagonal Architecture due to dynamic DI wiring. To compensate, we currently mask generic names like `path` and `text` in `pyproject.toml`, which creates silent technical debt. By retiring Vulture and relying on coverage, we can purge these blind spots and ensure all code is "alive" by proving it is tested.

## Deliverables
- [ ] **Cleanup** - Remove `vulture` from `tool.poetry.group.dev.dependencies` in `pyproject.toml`.
- [ ] **Cleanup** - Delete `tests/harness/vulture_whitelist.py`.
- [ ] **Cleanup** - Remove `vulture` hook from `.pre-commit-config.yaml`.
- [ ] **Refactor** - Purge the `ignore_names` and `per-file-ignores` (specifically for the whitelist) from the `[tool.vulture]` block in `pyproject.toml`. Delete the entire `[tool.vulture]` section.
- [ ] **Documentation** - Update `docs/architecture/ARCHITECTURE.md` to:
    - Remove `vulture` from the "Pre-commit Hooks" and "CI Quality Gates" sections.
    - Add a section on "Behavioral Proof of Life" explaining that dead code detection is enforced via 90%+ coverage and Ruff's static checks.
- [ ] **Verification** - Run `poetry run pytest --cov=src` to ensure coverage reporting is functional.

## Guidelines
- Ensure that removing Vulture doesn't break the CI pipeline.
- Be surgical in `pyproject.toml` to avoid disrupting other tool configurations.
