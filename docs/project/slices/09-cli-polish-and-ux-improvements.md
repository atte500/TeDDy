# Slice 09: CLI Polish & UX Improvements

## 1. Business Goal
**Source Milestone:** [08-core-refactoring-and-enhancements](/docs/project/milestones/08-core-refactoring-and-enhancements.md)

This final slice of Milestone 08 focuses on the "Professional Grade" polish of the TeDDy CLI. It addresses two areas:
1.  **Discoverability:** Enhancing `typer` help descriptions and docstrings to provide clear, actionable guidance for users.
2.  **Clarity during Execution:** Reducing cognitive load during interactive execution by consolidating multiple surgical `EDIT` operations into a single "Before vs. After" diff and simplifying the preview for new file `CREATE` actions.

## 2. Acceptance Criteria (Scenarios)

### Scenario: CLI help is descriptive and accurate
- **Given** the `teddy` CLI
- **When** a user runs `teddy --help` or `teddy execute --help`
- **Then** the output contains clear descriptions for all commands and options.
- **And** the descriptions accurately reflect the project's root-relative path requirements.

### Scenario: EDIT actions show a unified diff
- **Given** a plan with an `EDIT` action containing multiple `FIND`/`REPLACE` pairs
- **When** the plan is executed interactively
- **Then** the CLI displays exactly one diff for that file.
- **And** the diff correctly represents the cumulative result of applying all pairs in sequence.

### Scenario: CREATE actions show a simple preview
- **Given** a plan with a `CREATE` action
- **When** the plan is executed interactively
- **Then** the CLI displays a "New File Preview" with the full content of the file.
- **And** it does not attempt to show a diff against an empty/null source.

## 3. User Showcase
1. Run `teddy execute --help` to verify improved documentation.
2. Prepare a plan with an `EDIT` action having 2+ pairs. Run `teddy execute plan.md` (interactive) and verify only one diff block appears.
3. Prepare a plan with a `CREATE` action. Run `teddy execute plan.md` and verify the "New File Preview" header and content.

## 4. Architectural Changes

### Core Logic Migration
-   **New Port & Service:** Create `IEditSimulator` and `EditSimulator` in the core service layer. This service will encapsulate the logic for applying `FIND`/`REPLACE` pairs to a string.
-   **Refactor `LocalFileSystemAdapter`:** Update `edit_file` to delegate the string manipulation to the `EditSimulator`, keeping the adapter focused strictly on file I/O.

### CLI UX Refinement
-   **`ExecutionOrchestrator`:**
    -   Inject `IEditSimulator`.
    -   In `_confirm_and_dispatch_action`, generate a `ChangeSet` for `CREATE` and `EDIT` actions.
    -   Pass the `ChangeSet` to `user_interactor.confirm_action`.
-   **`ConsoleInteractorAdapter`:**
    -   Inject `ISystemEnvironment`.
    -   Remove direct imports of `os`, `shutil`, `subprocess`, and `tempfile`.
    -   Use the provided `ChangeSet` to display unified diffs or "New File Previews".
-   **`CLI Adapter` (`__main__.py`):**
    -   Enhance Typer command docstrings and help parameters for `execute`, `context`, and `get-prompt`.
    -   Ensure all help text emphasizes the project-root-relative path convention.

## 5. Scope of Work

### Phase 1: Edit Simulation Logic
- [x] Create `src/teddy_executor/core/ports/inbound/edit_simulator.py` defining the `IEditSimulator` protocol.
- [x] Create `src/teddy_executor/core/services/edit_simulator.py` implementing the logic.
- [x] Add unit tests for `EditSimulator` in `tests/unit/core/services/test_edit_simulator.py`.
- [x] Update `src/teddy_executor/container.py` to register the new service.

### Phase 2: Refactor Existing Edits
- [ ] Update `src/teddy_executor/adapters/outbound/local_file_system_adapter.py` to use `IEditSimulator`.
- [ ] Verify existing `EDIT` tests pass.

### Phase 3: CLI UX Improvements
- [ ] Update `src/teddy_executor/adapters/outbound/console_interactor.py`:
    - [ ] Inject `IEditSimulator` into the constructor.
    - [ ] Update `_get_diff_content` to apply all edits using the simulator.
    - [ ] Refactor `_show_in_terminal_diff` to provide a "New File Preview" for `CREATE` actions.
- [x] Update `src/teddy_executor/__main__.py`:
    - [x] Refine help strings for all commands and options.
- [ ] Add acceptance tests in `tests/acceptance/test_cli_polish.py` to verify unified diffs and new file previews.
