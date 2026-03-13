# Slice: Polishing UX and Logic Improvements
- **Status:** Completed
- **Milestone:** [docs/project/milestones/09-interactive-session-and-config.md](/docs/project/milestones/09-interactive-session-and-config.md)
- **Specs:** [docs/project/specs/plan-format-validation.md](/docs/project/specs/plan-format-validation.md), [docs/project/specs/report-format.md](/docs/project/specs/report-format.md)

## 1. Business Goal
Enhance the TeDDy CLI user experience by improving error visibility during parsing, cleaning up the visual presentation of reports, and making the interactive `PROMPT` action more flexible and editor-friendly.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Multi-Highlight AST Mismatches [✓]
**Given** a plan with multiple structural errors (e.g., missing metadata list and wrong heading levels)
**When** the plan is parsed by `MarkdownPlanParser`
**Then** the resulting `InvalidPlanError` AST summary must include the `MISMATCH_INDICATOR` (` <--- MISMATCH`) on **every** node that deviated from the expected schema, not just the first one.

#### Deliverables
- [✓] Update `InvalidPlanError` in `src/teddy_executor/core/ports/inbound/plan_parser.py` to accept `offending_nodes: List[Any]` instead of a single node.
- [✓] Update `MarkdownPlanParser._format_structural_mismatch_msg` in `src/teddy_executor/core/services/markdown_plan_parser.py` to iterate through the list of offending nodes and apply the indicator to all matching indices in the AST summary.

**Implementation Notes:**
- Pluralized `InvalidPlanError.offending_nodes` and added backward compatibility via `offending_node` property.
- Refactored `MarkdownPlanParser._parse_strict_top_level` to scan the first 5 slots for all deviations from the expected schema before data extraction.
- Updated `_format_structural_mismatch_msg` to highlight all indices corresponding to the nodes in the `offending_nodes` list using robust `id()` matching.
- **Architectural Polish:**
    - Moved AST formatting and mismatch message generation logic from `MarkdownPlanParser` to `parser_infrastructure.py` to keep the parser service focused and under the SLOC limit.
    - Simplified `_parse_strict_top_level` by extracting schema validation into `_validate_top_level_schema` (resolving Ruff C901).
    - Hardened the parser against Bandit (removed `assert`) and Mypy (added explicit type guards for AST iterations and unpacking).
    - Updated `MarkdownPlanParser` to maintain a thin internal wrapper `_format_structural_mismatch_msg` for backward compatibility with existing unit tests.

---

### Scenario 2: Report Whitespace Sanitization [✓]
**Given** an execution report generated from a template
**When** the report is formatted by `MarkdownReportFormatter`
**Then** the final output must have all leading and trailing whitespace removed.
**And** all sequences of three or more newlines must be collapsed into exactly two newlines (ensuring a maximum of one "blank line" between any two blocks of content).

#### Deliverables
- [✓] Update `MarkdownReportFormatter.format` in `src/teddy_executor/core/services/markdown_report_formatter.py` to post-process the rendered string:
    - Apply `.strip()` to remove leading/trailing noise.
    - Apply a regex substitution: `re.sub(r'\n{3,}', '\n\n', rendered_report)`.

**Implementation Notes:**
- Updated `MarkdownReportFormatter.format` to include a post-processing pipeline.
- Implemented per-line `rstrip()` to ensure lines don't have trailing spaces which can interfere with Markdown rendering.
- Applied `strip()` to remove document-level leading/trailing newlines/whitespace.
- Used `re.sub(r"\n{3,}", "\n\n", sanitized)` to collapse multiple blank lines into a single one.
- Verified via unit tests (mocking template output) and acceptance tests (full CLI execution).

---

### Scenario 3: Enhanced PROMPT Interactive Flow [✓]
**Given** a `PROMPT` action is executed in interactive mode
**When** the user selects `e` to open the editor
**Then** the marker instruction in the temporary file must be wrapped in an HTML comment (`<!-- ... -->`) so it is hidden in Markdown previewers.
**And** the terminal must continue to allow a single-line reply even while the editor is open (or immediately after opening it), providing a fallback for quick responses.

#### Deliverables
- [✓] Update `ConsoleInteractorAdapter._get_input_from_editor` in `src/teddy_executor/adapters/outbound/console_interactor.py` to use `<!-- ... -->` as the marker.
- [✓] Refactor `ConsoleInteractorAdapter.ask_question` to support a non-blocking interaction loop, allowing quick terminal replies or background editor confirmation.
- [✓] Simplify empty response confirmation to a double-Enter pattern.

**Implementation Notes:**
- Updated `ISystemEnvironment` and `SystemEnvironmentAdapter` to support background command execution via `subprocess.Popen`.
- Refactored `ConsoleInteractorAdapter.ask_question` to use a non-blocking loop. Launching the editor ('e') now puts the interactor into an "Editor Opened" state while still accepting terminal input.
- Terminal replies now explicitly clean up any abandoned background editor files.
- Simplified empty response confirmation: the interactor now prompts to "Press [Enter] again to confirm" instead of the "y/n/e" loop.
- Integrated the HTML comment marker (`<!-- ... -->`) into the background editor flow.

---

### Scenario 4: Dynamic PROMPT UI Header [✓]
**Given** a `PROMPT` action is executed
**When** the user is presented with the message in the terminal
**Then** the header must be formatted as `--- MESSAGE from [AGENT NAME] ---` in cyan.
**And** if no agent name is provided (e.g., during initial session prompt), it must default to `--- MESSAGE from TeDDy ---`.

#### Deliverables
- [✓] Update `IUserInteractor.ask_question` in `src/teddy_executor/core/ports/outbound/user_interactor.py` to accept an optional `agent_name: Optional[str] = None`.
- [✓] Update `ConsoleInteractorAdapter.ask_question` in `src/teddy_executor/adapters/outbound/console_interactor.py` to use the dynamic header with the "TeDDy" fallback.
- [✓] Update `ActionExecutor` (or the relevant service) to pass the `Agent` from the plan metadata to the interactor.

**Implementation Notes:**
- Propagated `agent_name` from `ExecutionOrchestrator` through `ActionExecutor` and `ActionDispatcher` to the `PROMPT` action.
- Updated `IUserInteractor.ask_question` signature and `ConsoleInteractorAdapter` implementation.
- Hardened `ActionDispatcher` to only pass `agent_name` to the `PROMPT` action to prevent `TypeError` on other action types.
- Updated all existing prompt tests (acceptance, unit, integration) to align with the new signature, stderr output, and HTML comment marker.

## 3. Architectural Changes
- `InvalidPlanError`: Update attribute to `offending_nodes: List[Any]`.
- `IUserInteractor.ask_question`: Add `agent_name: Optional[str] = None` parameter.
- Pure logic/template refinements in the service and adapter layers.
