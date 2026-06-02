# Slice: 02-05-Architecture Efficiency

- **Status:** In Progress
- **Type:** Refactor
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Business Goal
Optimize session storage and prompt management to reduce redundancy and improve session lifecycle performance.

## Deliverables
- [x] **Contract** - Ensure `preserve_message_turns: true` is supported in `config.yaml` and default service settings.
- [x] **Logic** - Update `SessionService._clone_session_artifacts` to remove the redundant cloning of `.xml` prompts into turn directories.
- [x] **Logic** - Update `SessionOrchestrator.execute` to resolve prompt content from the session root (parent directory) when fetching instructions.
- [x] **Logic** - Update `SessionPruningService` to strictly respect the `preserve_message_turns` configuration.
- [ ] **Logic** - Implement automatic session termination in `SessionOrchestrator` if the user provides an empty message response.
- [ ] **Refactor** - Standardize on session-root prompt naming (e.g. `system_prompt.xml`) across all services.
- [ ] **Cleanup** - Port existing session tests to verify that turn directories now only contain `input.md`, `plan.md`, `report.md`, and `meta.yaml`.

## Implementation Notes
- **Discovery (Prompt Relocation)**: Audited `SessionService` and confirmed standard transitions (01->02) and migrations (99->01) are already targeting the session root for agent prompts. However, identified several stale tests in `tests/suites/unit/core/services/` that still assert turn-local prompt existence.
