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

### Scenario 3: Resilient EDIT Matching
**Given** an `EDIT` action where the `FIND` block has minor whitespace differences from the source file
**When** validation is run
**Then** the system should identify the closest match using a `Similarity Threshold` of 0.8.
**And** if multiple candidates meet the threshold, the one with the highest `Similarity Score` must be selected.
**And** if there is a tie for the highest score, validation must fail for ambiguity.
**And** if it's a fuzzy match (Score < 1.0), the Execution Report must include a unified diff of the change.

#### Deliverables
- [ ] Updated `EditActionValidator` in `edit.py` to handle priority-based matching.
- [ ] Updated `find_best_match_and_diff` in `edit_matcher.py` to return the score.
- [ ] Updated `ActionExecutor` to inject diffs into `ActionLog` for fuzzy `EDIT`s.
- [ ] TDD suite for ambiguity and priority logic.

### Scenario 4: Granular EXECUTE Failure Reporting
**Given** an `EXECUTE` block with multiple commands (e.g., `cmd1\ncmd2`)
**When** `cmd2` fails
**Then** the `ActionLog` details must contain `failed_command: "cmd2"`.

#### Deliverables
- [ ] POSIX implementation in `ShellAdapter` using `set -e` and `trap '...' ERR`.
- [ ] Windows implementation in `ShellAdapter` using `%ERRORLEVEL%` checks.
- [ ] Acceptance test with a multi-line failing shell script.

## 3. Architectural Changes
- **Parser Layer:** Logic moved from block-level to line-level for `RESEARCH`.
- **Validation Layer:** `EditActionValidator` now uses scoring to resolve candidate selection.
- **Adapter Layer:** `ShellAdapter` transforms simple command strings into "Diagnostic Wrappers" before execution.
