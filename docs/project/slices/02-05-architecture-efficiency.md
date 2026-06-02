# Slice: 02-05-Architecture Efficiency

- **Status:** Planned
- **Type:** Refactor
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Business Goal
Optimize session storage and prompt management to reduce redundancy and improve session lifecycle performance.

## Deliverables
- [ ] **Contract** - Add `message_pruning: false` to `config.yaml` and default service settings.
- [ ] **Logic** - Update `SessionService._clone_session_artifacts` to remove the redundant cloning of `.xml` prompts into turn directories.
- [ ] **Logic** - Update `SessionOrchestrator.execute` to resolve prompt content from the session root (parent directory) when fetching instructions.
- [ ] **Logic** - Update `SessionPruningService` to respect the `message_pruning` configuration.
- [ ] **Refactor** - Standardize on session-root prompt naming (e.g. `system_prompt.xml`) across all services.
- [ ] **Cleanup** - Port existing session tests to verify that turn directories now only contain `input.md`, `plan.md`, `report.md`, and `meta.yaml`.
