# Slice: Simplify EXECUTE Action Syntax

- **Status:** Completed
- **Milestone:** [08-core-refactoring-and-enhancements](/docs/project/milestones/08-core-refactoring-and-enhancements.md)
- **Spec:** [New Plan Format](/docs/project/specs/new-plan-format.md)

## 1. Business Goal & Interaction Sequence
**Goal:** To improve developer and AI ergonomics by removing explicit `cwd` and `env` parameters from the `EXECUTE` action's metadata list. Instead, allow the AI to use natural POSIX `cd <path>` and `export KEY=VALUE` syntax directly inside the shell code block. A POSIX Shell Pre-Processor in the parser will intercept these, map them to internal execution parameters, and strip them from the raw command sent to the OS.

**Interaction:**
1.  **AI:** Generates a plan with an `EXECUTE` action containing `cd some/dir` and `export VAR=value` at the top of its shell block.
2.  **System:** `MarkdownPlanParser` processes the shell block, extracting the `cd` path into the `cwd` parameter, the `export` definitions into the `env` dictionary, and strips these directive lines.
3.  **System:** The execution proceeds seamlessly using the extracted `cwd` and `env` parameters.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Parsing `cd` for Working Directory
**Given** an `EXECUTE` action with a shell block starting with `cd src/my_dir`
**When** the plan is parsed
**Then** the `ExecuteAction` object must have its `cwd` property set to `src/my_dir`
**And** the `cd src/my_dir` line must be removed from the parsed command string.

### Scenario 2: Parsing `export` for Environment Variables
**Given** an `EXECUTE` action with a shell block starting with `export FOO=bar` and `export BAZ="qux"`
**When** the plan is parsed
**Then** the `ExecuteAction` object must have its `env` property containing `{"FOO": "bar", "BAZ": "qux"}`
**And** the `export` lines must be removed from the parsed command string.

### Scenario 3: Mixed Shell Block with Commands
**Given** an `EXECUTE` action with `cd tests`, `export CI=true`, and `pytest`
**When** the plan is parsed
**Then** `cwd` is `tests`, `env` contains `{"CI": "true"}`, and the remaining command is exactly `pytest`.

## 3. User Showcase
*To verify this feature manually:*
1. Create a dummy test file `target.txt` in a subdirectory `test_dir/`.
2. Write a plan with an `EXECUTE` action containing:
   ```shell
   cd test_dir
   export TEST_VAR=123
   echo $TEST_VAR > result.txt
   ```
3. Run `teddy execute --plan-content "$(cat plan.md)"`.
4. Verify the `result.txt` file was created inside `test_dir/` and contains `123`.

## 4. Architectural Changes

### `MarkdownPlanParser`
The parser will be updated to include an `_extract_posix_headers` helper method. This method will process the raw shell command string before it is attached to the `ExecuteAction`.
-   **Strict Header Block Extraction:** It will iterate line-by-line, extracting `cd <path>` and `export KEY=value` directives. It will ignore empty lines and comments (`#`). The extraction stops immediately upon encountering the first non-directive line (e.g., a normal command), leaving any subsequent `cd` or `export` statements intact within the script.
-   **Graceful Fallback:** If legacy `cwd` or `env` parameters are present in the action's metadata list, they will be used as the base state. Any directives found in the shell block header will override these legacy values.

### `New Plan Format Spec`
The official specification will be updated to deprecate the explicit `cwd` and `env` metadata fields for the `EXECUTE` action, demonstrating the new POSIX shell syntax.

## 5. Scope of Work

1.  **Update Specification:**
    -   Edit `docs/project/specs/new-plan-format.md` section 5.4 (`EXECUTE`). Remove `cwd` and `env` from the metadata format and add `cd` and `export` to the example shell block.
2.  **Implement POSIX Pre-Processor:**
    -   Add the `_extract_posix_headers` helper to `src/teddy_executor/core/services/markdown_plan_parser.py`.
    -   Update `_parse_execute_action` to pass the extracted legacy `cwd`/`env` and the raw command string to this new helper.
    -   Update the `params` dictionary with the unified `cwd`, `env`, and the stripped `command`.
3.  **Update Unit Tests:**
    -   In `tests/unit/core/services/test_markdown_plan_parser.py`, add comprehensive tests for the `EXECUTE` action to verify:
        -   Correct extraction of `cd` and `export` (including quoted values).
        -   Strict header enforcement (stopping at the first real command).
        -   Graceful fallback (merging legacy metadata with shell directives).
        -   Preservation of comments and blank lines within the retained script.

## Implementation Summary
This slice was implemented successfully following a strict, outside-in TDD workflow. The core logic was built through a series of three small, atomic TDD cycles, each resulting in a commit to the main trunk:
1.  **`cd` Directive:** A failing test was written to parse the `cd` directive, followed by the minimal implementation in a new `_extract_posix_headers` helper method.
2.  **`export` Directive:** A failing test was written to parse `export` directives (including quoted values), and the helper method was extended to support it.
3.  **Mixed Directives:** A final verification test was added to ensure both directives worked correctly together, which passed without requiring further implementation changes, acting as a valuable regression test.

The specification document `docs/project/specs/new-plan-format.md` was found to be already up-to-date, so no changes were required there. The `MarkdownPlanParser`'s component documentation was also found to be current.

### T3 Opportunities
- **Inconsistent Metadata Handling:** The `MarkdownPlanParser`'s handling of the `Description` metadata is inconsistent across different action parsers. Some methods add it back to the `params` dictionary after parsing, while others do not. This should be harmonized in a future refactoring slice to improve consistency.
