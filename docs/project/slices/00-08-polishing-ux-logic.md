# Slice: Polishing UX and Logic Improvements
- **Status:** Planned
- **Milestone:** [docs/project/milestones/09-interactive-session-and-config.md](/docs/project/milestones/09-interactive-session-and-config.md)
- **Specs:** [docs/project/specs/plan-format-validation.md](/docs/project/specs/plan-format-validation.md), [docs/project/specs/report-format.md](/docs/project/specs/report-format.md)

## 1. Business Goal
Enhance the TeDDy CLI user experience by improving error visibility during parsing, cleaning up the visual presentation of reports, and making the interactive `PROMPT` action more flexible and editor-friendly.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Multi-Highlight AST Mismatches
**Given** a plan with multiple structural errors (e.g., missing metadata list and wrong heading levels)
**When** the plan is parsed by `MarkdownPlanParser`
**Then** the resulting `InvalidPlanError` AST summary must include the `MISMATCH_INDICATOR` (` <--- MISMATCH`) on **every** node that deviated from the expected schema, not just the first one.

#### Deliverables
- [ ] Update `InvalidPlanError` in `src/teddy_executor/core/ports/inbound/plan_parser.py` to accept `offending_nodes: List[Any]` instead of a single node.
- [ ] Update `MarkdownPlanParser._format_structural_mismatch_msg` in `src/teddy_executor/core/services/markdown_plan_parser.py` to iterate through the list of offending nodes and apply the indicator to all matching indices in the AST summary.

---

### Scenario 2: Report Whitespace Sanitization
**Given** an execution report generated from a template
**When** the report is formatted by `MarkdownReportFormatter`
**Then** the final output must have all leading and trailing whitespace removed.
**And** all sequences of three or more newlines must be collapsed into exactly two newlines (ensuring a maximum of one "blank line" between any two blocks of content).

#### Deliverables
- [ ] Update `MarkdownReportFormatter.format` in `src/teddy_executor/core/services/markdown_report_formatter.py` to post-process the rendered string:
    - Apply `.strip()` to remove leading/trailing noise.
    - Apply a regex substitution: `re.sub(r'\n{3,}', '\n\n', rendered_report)`.

---

### Scenario 3: Enhanced PROMPT Interactive Flow
**Given** a `PROMPT` action is executed in interactive mode
**When** the user selects `e` to open the editor
**Then** the marker instruction in the temporary file must be wrapped in an HTML comment (`<!-- ... -->`) so it is hidden in Markdown previewers.
**And** the terminal must continue to allow a single-line reply even while the editor is open (or immediately after opening it), providing a fallback for quick responses.

#### Deliverables
- [ ] Update `ConsoleInteractorAdapter._get_input_from_editor` in `src/teddy_executor/adapters/outbound/console_interactor.py` to use `<!-- --- Please enter your response above this line... --- -->` as the marker.
- [ ] Refactor `ConsoleInteractorAdapter.ask_question` to prompt for terminal input immediately after launching the editor command if the system environment supports non-blocking execution or if a "quick-reply" prompt is desired.

---

### Scenario 4: Dynamic PROMPT UI Header
**Given** a `PROMPT` action is executed
**When** the user is presented with the message in the terminal
**Then** the header must be formatted as `--- MESSAGE FROM [AGENT NAME] ---` in cyan.
**And** if no agent name is provided (e.g., during initial session prompt), it must default to `--- MESSAGE FROM TeDDy ---`.

#### Deliverables
- [ ] Update `IUserInteractor.ask_question` in `src/teddy_executor/core/ports/outbound/user_interactor.py` to accept an optional `agent_name: Optional[str] = None`.
- [ ] Update `ConsoleInteractorAdapter.ask_question` in `src/teddy_executor/adapters/outbound/console_interactor.py` to use the dynamic header with the "TeDDy" fallback.
- [ ] Update `ActionExecutor` (or the relevant service) to pass the `Agent` from the plan metadata to the interactor.

## 3. Architectural Changes
- `InvalidPlanError`: Update attribute to `offending_nodes: List[Any]`.
- `IUserInteractor.ask_question`: Add `agent_name: Optional[str] = None` parameter.
- Pure logic/template refinements in the service and adapter layers.
