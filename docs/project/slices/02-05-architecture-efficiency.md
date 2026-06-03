# Slice: 02-05-Architecture Efficiency

- **Status:** In Progress
- **Type:** Refactor
- **Milestone:** [docs/project/milestones/02-stability-and-polish.md](/docs/project/milestones/02-stability-and-polish.md)
- **Specs:** [docs/project/specs/stability-and-bugfixes.md](/docs/project/specs/stability-and-bugfixes.md)

## Business Goal
Optimize session storage and prompt management to reduce redundancy and improve session lifecycle performance.

## Deliverables
- [x] **Contract** - Ensure `preserve_message_turns: true` is supported in `config.yaml`.
- [x] **Logic** - Refactor `SessionService` and `SessionOrchestrator` to use dynamic agent naming (e.g., `pathfinder.xml`) at the session root.
- [x] **Logic** - Strictly deprecate prompt cloning; `SessionService._clone_session_artifacts` MUST NOT copy prompts into turn directories.
- [x] **Logic** - Implement session termination in `SessionOrchestrator` main loop if user message is empty; ensure NO `report.md` is created to allow clean resume.
- [ ] **Logic** - Ensure `SessionPruningService` strictly respects `preserve_message_turns`.
- [ ] **Cleanup** - Update all stale session tests to verify that turn directories only contain `input.md`, `plan.md`, `report.md`, and `meta.yaml`.

## Implementation Notes
- **Discovery (Prompt Relocation)**: Audited `SessionService` and confirmed standard transitions (01->02) and migrations (99->01) are already targeting the session root for agent prompts. However, identified several stale tests in `tests/suites/unit/core/services/` that still assert turn-local prompt existence.
- **Verification (Contract Test)**: Created `test_session_service_prompt_contract.py` to formally enforce the session-root prompt placement rule. The test passes immediately, confirming the architecture integrity. The cloning logic exclusively writes `.xml` files to `dest_session` without referencing `dest_turn`.
- **Verification (Dynamic Agent Naming)**: Created `test_session_service_dynamic_agent_naming.py` to assert that `create_session` writes the agent prompt to the session root using the dynamic agent name (e.g., `architect.xml`) rather than a hardcoded filename or turn-local path. The test passes immediately, confirming the architecture already satisfies the requirement.
- **Empty Message Termination**: Implemented early-return guard in `SessionOrchestrator.execute()` (after docstring, before any logic) that returns `None` if `message` is not None but whitespace-only. Created unit test `test_session_orchestrator_empty_message.py` verifying that no `report.md` is written and `None` is returned. This ensures clean session termination per the spec (handoff-protocol.md: "If the user provides an empty response, the session terminates.").
