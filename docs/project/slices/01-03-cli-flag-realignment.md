# Slice: 01-03-CLI Flag Realignment

- **Status:** Planned
- **Milestone:** [docs/project/milestones/01-structural-message-protocol.md](/docs/project/milestones/01-structural-message-protocol.md)
- **Specs:** [docs/project/specs/interactive-session-workflow.md](/docs/project/specs/interactive-session-workflow.md)

## Business Goal
Enable the `start` command to accept a `-c/--context` flag and LLM overrides (`--model`, `--provider`, `--api-key`), ensuring full spec compliance and allowing users (and agents) to customize session-specific behavior.

## Scenarios
> As a User, I want to provide specific context files when starting a session so that the AI is immediately oriented.

```gherkin
Given a project with files "src/main.py" and "docs/README.md"
When I run "teddy start -c src/main.py,docs/README.md"
Then a new session is created
And the "session.context" file contains both paths
```

## Edge Cases
- **Invalid Paths**: If a path provided in `-c` does not exist, the command should notify the user but proceed if other paths are valid.
- **Directory Expansion**: If a directory is provided, it should be expanded recursively (delegated to `ContextService`).

- **Component Docs:** [docs/architecture/core/ports/outbound/session_manager.md](/docs/architecture/core/ports/outbound/session_manager.md), [docs/architecture/core/services/session_service.md](/docs/architecture/core/services/session_service.md)

## Deliverables
- [x] **Contract** - Update `ISessionManager.create_session` to accept `additional_context: Optional[list[str]] = None` and LLM overrides (`model`, `provider`, `api_key`).
- [x] **Harness** - Create `tests/suites/acceptance/test_cli_context_flag.py` to verify `start -a`, `-m`, `-c`, and LLM overrides.
- [x] **Logic** - Update `SessionService.create_session` to merge `additional_context` into `session.context` and persist overrides in `meta.yaml`.
- [x] **Logic** - Update `PlanningService.generate_plan` to extract `provider` and `api_key` from metadata and pass them to `llm_client.get_completion`.
- [x] **Wiring** - Update `handle_new_session` in `session_cli_handlers.py` to accept and pass the new flag values.
- [x] **Wiring** - Fix `start` command in `src/teddy_executor/__main__.py`: explicitly add `-a` short flag for `--agent` and add `-c` for the new `--context` flag. Ensure `--model`, `--provider`, and `--api-key` are also wired.
- [x] **Cleanup** - Verify through integration tests that all flags (including short aliases) are correctly propagated and persisted.
- [x] **Refactor** - [DEBT] Consolidate `create_session` parameters (7) into a DTO (e.g., `SessionOptions`) to satisfy `PLR0913`.

## Implementation Notes

### Deliverable: Refactor - Consolidate create_session parameters into a DTO
- **DTO Implementation**: Created `SessionOptions` DTO in `src/teddy_executor/core/domain/models/session.py` to encapsulate all session initialization parameters.
- **Interface Decoupling**: Updated `ISessionManager` and `SessionService` to use the DTO, reducing constructor complexity and satisfying `PLR0913`.
- **Migration**: Updated all call sites including `session_cli_handlers.py` and the full unit test suite.
- **Contract Enforcement**: Updated `test_session_manager_contract.py` to verify the new signature at the protocol level.

### Deliverable: CLI Flag Realignment and Persistence
- **Flag Wiring**: Added `-c/--context`, `--model`, `--provider`, and `--api-key` to the `start` command in `__main__.py`. Added `-a` short alias for `--agent`.
- **Pre-flight UX**: Refactored `handle_new_session` to perform LLM configuration checks *before* prompting for a message, ensuring a fail-fast experience. Restored the "Checking configurations..." message required by acceptance tests.
- **Persistence**: Enhanced `SessionService` to persist LLM overrides in `meta.yaml` and carry them forward. Updated `PromptManager` to respect these overrides during turn transitions.
- **Robustness**: Modified `scrub_dict_for_serialization` to neutralize mock objects into `"mock_object"`, preventing test-harness leakage into persistent storage.
- **DI Purity**: Fixed a regression in `InitService` by ensuring it uses the `IFileSystemManager` port instead of native `open()`/`os.path` for reading default templates.

### Deliverable: Contract - ISessionManager.create_session
- Updated ISessionManager protocol in src/teddy_executor/core/ports/outbound/session_manager.py to include optional parameters: additional_context, model, provider, and api_key.
- Applied @runtime_checkable to ISessionManager to enable runtime validation in tests.
- Updated SessionService.create_session signature in src/teddy_executor/core/services/session_service.py to match the protocol.
- Verified non-breaking nature of the change via a global test run and specific contract tests in tests/suites/unit/core/ports/test_session_manager_contract.py.

### Deliverable: Wiring - CLI Flags and Persistence
- Wired `-c/--context`, `--model`, `--provider`, and `--api-key` flags in `src/teddy_executor/__main__.py`.
- Updated `handle_new_session` in `src/teddy_executor/adapters/inbound/session_cli_handlers.py` to propagate flags to the `SessionService`.
- Enhanced `SessionService` in `src/teddy_executor/core/services/session_service.py` to persist overrides in `01/meta.yaml` and carry them forward during turn transitions/re-plans.
- Fixed `PromptManager.update_meta` in `src/teddy_executor/core/services/prompt_manager.py` to respect existing metadata overrides for the `model` field.
- Hardened `scrub_dict_for_serialization` in `src/teddy_executor/core/utils/serialization.py` to neutralize mock objects into `"mock_object"`, preventing test-harness leakage into persisted metadata.
- Verified all behaviors via acceptance tests in `tests/suites/acceptance/test_cli_context_flag.py`.
