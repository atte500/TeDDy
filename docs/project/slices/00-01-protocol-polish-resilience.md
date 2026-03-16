# Slice: Protocol Polish & Resilience (Fast-Track)

- **Status:** Planned
- **Milestone:** N/A (Fast-Track)
- **Specs:** [docs/project/specs/plan-format.md](/docs/project/specs/plan-format.md), [docs/project/specs/plan-format-validation.md](/docs/project/specs/plan-format-validation.md), [docs/project/specs/report-format.md](/docs/project/specs/report-format.md)

## 1. Business Goal
To streamline the AI coding workflow by making the Markdown protocol more flexible for the AI (READ alias), more resilient to minor discrepancies (EDIT fuzzy matching), and more diagnostic for complex operations (EXECUTE failure reporting).

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Flexible Resource Parsing (READ/PRUNE)
**Given** a plan with a `READ` or `PRUNE` action using `- **File Path:** [path/to/file](/path/to/file)`
**When** the plan is parsed
**Then** the `path` or `resource` parameter should be correctly populated.
**And** if a URL is provided under `File Path`, validation should fail with a "Strict Local Only" error.

#### Deliverables
- [✓] Updated `parse_resource_action` in `action_parser_strategies.py` (shared by READ/PRUNE).
- [✓] New validation rule in `READ` validator for the `File Path` constraint.
- [✓] New validation rule in `PRUNE` validator for the `File Path` constraint.
- [✓] Updated acceptance tests to cover both `READ` and `PRUNE` aliases.
- [✓] Unit tests for alias parsing and URL constraint.

#### Implementation Notes
- **Shared Parsing:** `parse_resource_action` was updated to support the `File Path` alias, which is shared by both `READ` and `PRUNE` actions.
- **Metadata Flagging:** The parser now sets an internal `metadata_used_file_path_alias` flag in the action parameters.
- **Validation Constraint:** Both `ReadActionValidator` and `PruneActionValidator` now enforce a "Strict Local Only" policy when the alias is used, rejecting URLs.
- **Infrastructure Safety:** `ActionDispatcher` filters out all parameters prefixed with `metadata_` before execution to prevent `TypeError`s in infrastructure adapters.

### Scenario 2: Multi-line RESEARCH Handling
**Given** a `RESEARCH` block containing multiple lines of queries
**When** the plan is parsed
**Then** the `queries` parameter should contain a list of individual queries, one per line.

#### Deliverables
- [✓] Updated `parse_research_action` in `action_parser_complex.py` to split by newline.
- [✓] Integration test verifying multiple queries are generated from a single block.

#### Implementation Notes
- **Line-based Splitting:** `parse_research_action` now iterates over each line of a code block's content, stripping whitespace and filtering out empty lines.
- **Backwards Compatibility:** It continues to support multiple code blocks, aggregating all discovered queries into a single list.

### Scenario 3: Resilient EDIT Matching [✓]
**Given** an `EDIT` action where the `FIND` block has minor whitespace differences from the source file
**When** validation is run
**Then** the system should identify the closest match using a `Similarity Threshold` (default: 0.95).
**And** if multiple candidates meet the threshold, the one with the highest `Similarity Score` must be selected.
**And** if there is a tie for the highest score, validation must fail for ambiguity.
**And** if it's a fuzzy match (Score < 1.0), the Execution Report must include a unified diff of the change.

#### Deliverables
- [✓] Multi-layered matching heuristics in `edit_matcher.py` (Exact -> Fuzzy Cascade -> Exhaustive).
- [✓] Performance optimization (Priority Capping & Sub-sampling) in `edit_matcher.py`.
- [✓] Update `parse_edit_action` in `action_parser_complex.py` to extract `Similarity Threshold` from metadata.
- [✓] Update `find_best_match_and_diff` signature to accept `threshold: float` and return `(diff: str, score: float, is_ambiguous: bool)`.
- [✓] Update `EditActionValidator` to pass the parsed threshold to the matcher and handle the `is_ambiguous` flag.
- [✓] Update `ActionExecutor._inject_execution_diff` to inject unified diffs for all successful `EDIT` actions.
- [✓] TDD suite for ambiguity (tie-breaking) and threshold override logic.

#### Implementation Notes
- **Unified Matching Engine:** `edit_matcher.py` was refactored to expose `find_best_match`, which is now shared by the `EditActionValidator` (for diagnostics) and the `EditSimulator` (for execution).
- **High-Fidelity Threshold:** Based on regression analysis, the default `Similarity Threshold` was unified to **0.95** across the entire stack (Validator, Port, Adapter, and Simulator) to ensure predictable behavior while remaining resilient to minor AI formatting errors.
- **Custom Thresholds:** The parser now extracts `- **Similarity Threshold:**` from `EDIT` metadata. This parameter is passed through the validator, the `IFileSystemManager` port, and finally to the simulator.
- **Enhanced Diagnostics:** Validation errors for `EDIT` now include the `Similarity Score` and the current `Similarity Threshold`. If a tie is detected (Ambiguity), the error specifically instructs the user/AI to provide a larger `FIND` block.
- **Surgical Matching (Substring Boost):** The matcher was enhanced to support surgical intra-line replacements. If a single-line `FIND` block matches a substring exactly, it is boosted to a 1.0 score, returning only the matching substring to prevent whole-line replacements.
- **Reporting Transparency:** `ActionExecutor` now automatically generates and injects a unified diff for *every* successful `EDIT` action into the final report, providing immediate visual feedback of the applied changes.
- **Execution Resilience:** The `EditSimulator` was upgraded from exact string counting to fuzzy matching, ensuring that if a plan passes fuzzy validation, it will also succeed during the execution phase.

### Scenario 4: Granular EXECUTE Failure Reporting [✓]
**Given** an `EXECUTE` block with multiple commands (e.g., `cmd1\ncmd2`)
**When** `cmd2` fails
**Then** the `ActionLog` details must contain `failed_command: "cmd2"`.

#### Deliverables
- [✓] POSIX implementation in `ShellAdapter` using a function-based `DEBUG`/`EXIT` trap wrapper for high granularity.
- [✓] Windows implementation in `ShellAdapter` using `&&` logic and `FAILED_COMMAND` markers.
- [✓] Acceptance test with a multi-line failing shell script.
- [✓] Unit tests verifying sub-command isolation within `&&` chains.

#### Implementation Notes
- **Diagnostic Wrappers:** `ShellAdapter` now automatically wraps multi-line and chained command strings in platform-specific diagnostic scripts.
- **POSIX (Bash):** Uses a sophisticated diagnostic script with a `DEBUG` trap to capture the `BASH_COMMAND` before execution and an `EXIT` trap (handled by a shell function to prevent pollution) that reports the last attempted sub-command if the shell terminates with a non-zero status. This provides sub-command level granularity even within `&&` chains.
- **Windows (CMD):** Joins commands with `&&` and injects `|| (echo FAILED_COMMAND: ... >&2 && exit /b 1)` for each line to ensure "fail-fast" behavior and identification.
- **Extraction Logic:** The adapter parses the stderr of the command execution to find the `FAILED_COMMAND` marker and populates the `failed_command` field in the `ShellOutput` DTO.
- **Reporting:** The Execution Report template renders the `failed_command` prominently in the Action Log when present.

### Scenario 5: Success Transparency & Multi-Instance Replacement [✓]
**Given** an `EDIT` action is successful
**When** the execution report is generated
**Then** it must include the `Similarity Score` even if the score is 1.0.

**Given** an `EDIT` action with the parameter - **Replace All:** `true`
**When** executed
**Then** the system must replace *all* occurrences of the `FIND` block within the target file.
**And** it must still respect the `Similarity Threshold` for each match.
**And** if an ambiguous match is detected, the error message must include a specific hint recommending code refactoring and to use Replace All: `true` if intention is to change all occurrences in the file.

#### Deliverables
- [✓] Update `IMarkdownReportFormatter` and the Jinja2 template to include `similarity_score` in the successful action log.
- [✓] Update `EditAction` domain model to include a `replace_all` boolean field.
- [✓] Update `parse_edit_action` to extract `Replace All` from metadata.
- [✓] Update `EditSimulator` to handle multiple replacements when `replace_all` is true.
- [✓] Update `ActionExecutor` to aggregate scores/results for bulk edits.
- [✓] Refactor the ambiguity error message.

#### Implementation Notes
- **Hunk-Based Transparency:** Refactored `generate_character_diff` to use a windowing/merging algorithm. This ensures multi-site edits are shown clearly with `...` separators and no context duplication, resolving the "only one change shown" transparency issue.
- **Character-Level Diffs (`ndiff`):** Enabled surgical `ndiff` markers (`?`) for all fuzzy `EDIT` matches in the Execution Report, even in interactive mode, to provide high-fidelity audit trails.
- **Multi-Instance Replacement:** `EditSimulator` now supports `Replace All: true` metadata, which iterates through the file applying the replacement to every match meeting the `Similarity Threshold`.
- **Ambiguity Diagnostics:** Updated `MultipleMatchesFoundError` with a specific hint directing the user toward either code refactoring or the use of `Replace All`.
- **Reporting Polish:** Unified similarity score rendering in the Jinja2 template, ensuring scores are always present for successful `EDIT` actions to maintain transparency.
- **Diff Injection Resilience:** Upgraded `ActionExecutor` to automatically inject unified diffs for `CREATE` overwrites and character-level diffs for fuzzy `EDIT` matches. Diffs for perfect `EDIT` matches remain suppressed to reduce noise.

## 3. Architectural Changes
- **Parser Layer:** Logic moved from block-level to line-level for `RESEARCH`.
- **Validation Layer:** `EditActionValidator` now uses scoring to resolve candidate selection.
- **Adapter Layer:** `ShellAdapter` transforms simple command strings into "Diagnostic Wrappers" before execution.
