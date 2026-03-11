# Slice 00-06: CREATE Action Overwrite Parameter
- **Status:** Completed
- **Milestone:** N/A (Fast-Track)
- **Specs:** [docs/project/specs/plan-format.md](/docs/project/specs/plan-format.md), [docs/project/specs/plan-format-validation.md](/docs/project/specs/plan-format-validation.md)

## 1. Business Goal
Allow the `CREATE` action to optionally overwrite an existing file when explicitly requested via an `Overwrite: true` parameter. This prevents agents from being blocked when they need to completely replace a file, while still enforcing safety rails by requiring explicit intent and providing a clear diff of the destructive action.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Validation of standard CREATE (File Exists)
*   **Given** a plan with a `CREATE` action targeting a file that already exists
*   **And** the `Overwrite` parameter is omitted or `false`
*   **When** the plan is validated
*   **Then** validation must fail
*   **And** the failure message must explicitly state that the file exists and hint that the `Overwrite: true` parameter can be used with caution to bypass this.
#### Deliverables
*   *This section will be populated in a later step.*

### Scenario 2: Validation of CREATE with Overwrite (File Exists)
*   **Given** a plan with a `CREATE` action targeting a file that already exists
*   **And** the `Overwrite` parameter is `true`
*   **When** the plan is validated
*   **Then** validation must pass.
#### Deliverables
*   *This section will be populated in a later step.*

### Scenario 3: Execution and Diff Generation
*   **Given** a validated plan with a `CREATE` action targeting an existing file with `Overwrite: true`
*   **When** the plan is executed
*   **Then** the file's contents must be replaced with the new contents
*   **And** the generated execution report MUST include a unified diff showing the exact changes made to the file (similar to an `EDIT` action).
#### Deliverables
*   *This section will be populated in a later step.*

### Scenario 4: Documentation and Prompt Updates
*   **Given** the new functionality is implemented
*   **When** reviewing the project documentation
*   **Then** all agent prompts (`prompts/*.xml`) must be updated to document the optional `Overwrite: [true|false]` parameter under the `CREATE` action format, including a strong warning to use it cautiously.
*   **And** `plan-format.md` and `plan-format-validation.md` must be updated to reflect the new parameter and validation rules.
#### Deliverables
*   [✓] Updated `prompts/dev.xml`
*   [✓] Updated `prompts/architect.xml`
*   [✓] Updated `prompts/pathfinder.xml`
*   [✓] Updated `prompts/debugger.xml`
*   [✓] Updated `docs/project/specs/plan-format.md`
*   [✓] Updated `docs/project/specs/plan-format-validation.md`

## 3. Architectural Changes
*   **Action Domain Model:** Parsing logic in `action_parser_strategies.py` was updated to extract the `Overwrite` metadata key.
*   **ActionValidator:** `CreateActionValidator` now supports bypassing the file-existence check if `overwrite: True` is present.
*   **ActionExecutor / FileSystemManager:** The `IFileSystemManager` port and `LocalFileSystemAdapter` were updated to support an optional `overwrite` parameter in `create_file`.
*   **ActionExecutor:** Refactored to capture file state *before* execution, enabling unified diff generation for `CREATE` overwrites.
*   **Core Utils:** Introduced `src/teddy_executor/core/utils/diff.py` to centralize unified diff generation.
*   **MarkdownReportFormatter:** Jinja2 templates updated to render a `#### diff` section for file actions containing a diff in their log details.

## 4. Implementation Notes
*   **Safety Rails:** The `Overwrite` parameter is optional and defaults to `False`. Validation explicitly hints at the parameter when a file collision occurs.
*   **Diff Generation:** Unified diffs are generated only for `CREATE` actions that result in an overwrite. `EDIT` actions continue to show their `FIND`/`REPLACE` blocks in the report without a redundant unified diff.
*   **Headless Testing:** Acceptance tests for interactive components must use `mock_env` and `mock_user_interactor` to avoid triggering external editors or diff tools.

### Architectural Feedback
*   **Shared Utils:** The `ndiff` logic in `EditActionValidator` remains separate from the new `generate_unified_diff` utility because the former is specialized for "closest match" search. Consider future consolidation of all diffing logic into the `core/utils/diff.py` module.
*   **ChangeSet Timing:** The `ActionExecutor` now calculates the `ChangeSet` before execution. This is a critical pattern for any action requiring a before/after comparison in reports.
