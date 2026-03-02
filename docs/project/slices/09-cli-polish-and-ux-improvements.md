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
- **And** it uses the external editor for the preview if one is configured.
- **And** it does not attempt to show a diff against an empty/null source.

### Scenario: External diff previews preserve file extensions
- **Given** a plan with an `EDIT` action for a file with a specific extension (e.g., .py)
- **And** an external diff tool is configured
- **When** the plan is executed interactively
- **Then** the temporary files created for the diff tool must preserve the original file extension.

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
- [▶️] Update `src/teddy_executor/adapters/outbound/console_interactor.py`:
    - [x] Inject `IEditSimulator` into the constructor. (Actually already injected SystemEnvironment, logic for unified diff is handled via ChangeSet from Orchestrator)
    - [x] Update `_get_diff_content` to apply all edits using the simulator. (Handled in Orchestrator)
    - [x] Refactor `confirm_action` to provide a "New File Preview" for `CREATE` actions, even when external diff tool is available.
    - [x] Ensure temporary files for external diffs preserve the original file extension.
- [x] Update `src/teddy_executor/__main__.py`:
    - [x] Refine help strings for all commands and options.
- [✅] Add/Fix acceptance tests in `tests/acceptance/test_cli_polish.py` to verify unified diffs and new file previews.

## Implementation Notes

### Work Summary
Successfully implemented the "Professional Grade" CLI polish for Milestone 08.
- **Unified Diffing:** Sequential `EDIT` operations are now consolidated into a single "Before vs. After" diff view, reducing cognitive load during interactive approval.
- **Enhanced CREATE Previews:** New files now leverage the user's preferred external editor (e.g., VS Code) for single-file previews without triggering a split-pane diff against an empty source.
- **Syntax Highlighting:** Temporary preview files now preserve the original file's extension, ensuring the editor provides correct syntax highlighting.
- **OS Abstraction:** Decoupled CLI interaction from the host OS by introducing the `ISystemEnvironment` port, making the interactor pure and independently testable.
- **CLI Discoverability:** Polished all Typer help strings to explicitly mention the project-root-relative path requirement.

### Significant Refactoring
- **String Manipulation Extraction:** Moved the logic for applying surgical edits from the `LocalFileSystemAdapter` to a new `EditSimulator` service. This ensures that the content seen in previews is bit-for-bit identical to what is eventually written to disk.
- **Interactor Decoupling:** Removed all direct imports of `os`, `shutil`, `subprocess`, and `tempfile` from `ConsoleInteractorAdapter`, delegating these to the `ISystemEnvironment` port.

### New Opportunities
- **Text User Interface (TUI):** Explore using `Rich` or `Textual` to build a TUI for plan execution, providing an even more fluid and modern terminal experience than the current line-by-line prompt.
- **Configurable Diff Flags:** Allow users to specify custom flags for their diff tools in the environment variable (e.g., to support tools that use flags other than `--diff` or `-d`).
- **ChangeSet Expansion:** Extend the `ChangeSet` and `EditSimulator` to support `DELETE` and `RENAME` operations as the plan format matures.
