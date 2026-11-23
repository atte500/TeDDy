# Spec: Plan Format

## Overview

This format is designed to be a perfectly readable Markdown document first, and a machine-parseable plan second.

## Guiding Principles

1.  **Markdown-First:** The document uses standard Markdown headings (`#`, `##`, `###`) to create a readable structure. The layout should feel natural to anyone familiar with Markdown.
2.  **Single Source of Truth (SoT):** All data and metadata are written once directly in the visible Markdown content. There is no hidden or duplicated data.
3.  **Hierarchical Structure:** The plan is a hierarchy of components. The parser should walk the Markdown AST, and the content of any given heading level contains all sub-levels. For example, the `## Action Plan` section contains all the individual action blocks defined by `###` headings.

## Technical Specifications

### Overall Document Structure

#### Code Block Nesting

A core principle of this format is that it must reliably handle nested code blocks, which is a common source of errors in LLM-generated Markdown.

-   **The Problem:** If a code block's content contains a run of the same fence character (backticks or tildes) that is at least as long as the enclosing fence, the Markdown becomes invalid and cannot be parsed correctly.
-   **The Rule (Primary Defense):** A fenced code block may use either backticks or tildes, but its fence **must** be strictly longer than the longest run of the *same* fence character found anywhere inside the content. This mirrors the shared Markdown Response Protocol's rule and is the primary defense against parsing errors.
-   **System Support (Validation & Self-Correction):** To guarantee robustness, the system includes a pre-flight validation check that is **run automatically** by the `teddy execute` command. Before any plan is presented to the user for approval, the system first ensures it is well-formed and parsable. If parsing fails (e.g., due to an ambiguous code fence), it triggers the **Automated Re-plan Loop** which instructs the AI to correct its own formatting error. See the [Plan Validation & Automated Re-planning](/docs/project/specs/interactive-session-workflow.md#8-plan-validation--automated-re-planning) section for full details.

#### One Plan Per Response

A response carries exactly one plan document. It holds exactly one Level 1 (`#`) heading and exactly one of `## Action Plan` or `## Message`. A second plan document in the same response is forbidden, whether it repeats the title, restates the rationale, or offers an alternative set of actions after the first plan ends. Work that follows a completed plan belongs to the next turn; when a turn must weigh alternatives instead of acting, it returns a single `## Message` describing them.

A plan is a single Markdown file with the following top-level structure:

```markdown
# [Descriptive Plan Title]
- **Status:** ...
- **Agent:** ...
...

## Rationale
...

## Action Plan
... (Contains one or more action blocks)
```

### File Linking Conventions

To ensure links work correctly in local previews (like VSCode) while referencing the project root, a specific syntax must be used.

-   **Root-Relative Links (Required):** All links to files within the project must be relative to the project's root directory.
    -   **Syntax:** `[path/from/root](/path/from/root)`
    -   **Explanation:** The link text (in square brackets) is the path from the root *without* a leading slash. The link destination (in round brackets) is the same path *with* a leading slash.
    -   **Example:** `[docs/ARCHITECTURE.md](/docs/ARCHITECTURE.md)`
    -   **Behavior:** This specific structure ensures that the link text is displayed cleanly while the link itself resolves correctly from the project root in the previewer.

### Parameter Values

Metadata values are read from rendered Markdown, not from the raw source line. The renderer removes inline-code backticks and emphasis markers before extraction, so `- **Overwrite:** true`, `- **Overwrite:** `true``, and `- **Overwrite:** **true**` all reach the parser as the string `true`. No scrubbing pass is involved: the parser never strips backticks itself.

One deliberate exception and two coercion rules follow from that.

-   **Never emphasise a path.** For path-valued keys (`File Path`, `Resource`, `Source`, `Destination`, `Path`) the parser re-emits emphasis as underscores, because a file name may legitimately contain them (`__main__.py`). A bolded `**README.md**` therefore arrives as `__README.md__`, which is not the file. Write paths plainly, as an inline code span, or as a root-relative link; all three resolve to the path itself.
-   **Spell booleans as `true` or `false`.** Boolean parameters accept any capitalisation of `true` and treat every other value as `false`. `yes`, `1`, and `TRUE!` all read as false.
-   **Numeric parameters read a leading number.** `Timeout: 30 seconds` reads as `30`. A value with no leading number falls back to the configured default.

### Core Component Blocks

#### Plan Header

-   **Purpose:** Contains the plan's title and high-level metadata. It must be the first and only Level 1 (`#`) heading in the document.
-   **Format:**
    ```markdown
    # A Descriptive Plan Title
    - **Status:** Green 🟢
    - **Plan Type:** Implementation
    - **Agent:** Pathfinder
    ```
-   **Parsing Rules:** The plan's title is the content of the `#` heading. The metadata is the bulleted list that immediately follows it. The parser should treat this list as key-value pairs.

#### Rationale

-   **Purpose:** Contains the agent's reasoning, state, and thought process. It acts as a **cognitive forcing function** to ensure every plan is grounded, deliberate, and strategic.
-   **Format:** The `Rationale` block is a plain text code block that **must** contain four distinct sections, each with a `###` heading, in the following order: `### Summary`, `### Expectation`, `### Progress`, and `### Notes`.

    `````markdown
    ## Rationale
    ````text
    ### Summary
    [The whole story so far: what the session has established, what the previous turn's outcome means, and why this plan is the next logical step. Reason aloud to get there: interpret the previous turn's result, trace what it implies, and derive why this plan follows, instead of only restating the outcome. This section carries the complete context a reader needs to follow the current decision, not a recap of only the last turn.]

    ### Expectation
    [Observable outcome: State the single, specific, falsifiable result you expect from this action plan, and what it will prove about your current state or hypothesis. Then state how that outcome dictates the subsequent step: what you will do if it holds, and what you will do if it does not.]

    ### Progress
    [The goal, reference files, and the phase checklist for the current task.]

    ### Notes
    [TODO items, documentation gaps, constraints, open questions, and other tracked notes.]
    ````
    `````
-   **Parsing Rules:** The content is the raw text within the fenced code block and is primarily for human consumption and agent self-correction. Only the four `###` headings above delimit sections; any other heading or marker, including a numeric `1. Section`, is body text and merges into the preceding section. The outer fence for the `Rationale` block must follow the **Code Block Nesting** rule.

### Action Blocks

All actions are located under the `## Action Plan` heading. Each action is defined by its own `###` heading.

#### `CREATE`

-   **Purpose:** Creates a new file.
-   **Format:**
    `````markdown
    ### `CREATE`
    - **File Path:** [docs/project/specs/invariants/plan-format.md](/docs/project/specs/invariants/plan-format.md)
    - **Overwrite:** true
    - **Description:** Create the initial specification document.
    ````markdown
    # Specification: The Pure Markdown Plan Format
    ... file content ...
    ````
    `````
-   **Parameters:**
    -   `File Path`: The root-relative path to the file. Missing parent directories are created automatically.
    -   `Overwrite` (Optional): If `true`, allows replacing an existing file. Use with extreme caution.
    -   `Description`: A short summary of the action.
-   **Parsing Rules:**
    1.  Extract `File Path`, `Overwrite`, and `Description` from the metadata list.
    2.  The content for the new file is the entire content of the first fenced code block. The block is mandatory: a `CREATE` without it fails parsing before execution, while an empty block writes an empty file.
    3.  The target is always a file. A trailing slash does not denote a directory: `CREATE docs/notes/` writes a file named `notes`, and naming an existing directory fails at execution.

#### `READ`

-   **Purpose:** Reads a local file or remote URL to gather information.
-   **System Behavior:** A successful `READ` will cause the system to automatically add the target resource to the context for the *next* turn.
-   **Format:**
    ````markdown
    ### `READ`
    - **Resource:** [docs/ARCHITECTURE.md](/docs/ARCHITECTURE.md) or [www.example.com](https://example.com/docs)
    - **File Path:** [docs/ARCHITECTURE.md](/docs/ARCHITECTURE.md)
    - **Description:** Read the current architectural conventions.
    ````
-   **Parsing Rules:**
  1.  Extract `Resource` or `File Path` and `Description`.
  2.  `Resource` supports both local paths (starting with `/`) and URLs (starting with `http`).
  3.  `File Path` is an alias for local resources and **strictly forbids URLs**.
  4.  The value for either can be a root-relative Markdown link `[text](/destination)`.

#### `EDIT`

-   **Purpose:** Edits an existing file. It is strongly preferred to make surgical changes by including multiple, small, sequential `FIND`/`REPLACE` pairs in a single action rather than one large replacement.

##### Parser Resilience (Cross-Action)
For all actions, the parser must ignore and clean up unforeseen codeblocks or thematic breaks (`---`) following the action block without throwing validation errors. When at least one action has been parsed, the parser must strip a trailing run of paragraphs that reaches the document end. The parser must persist the stripped plan to the session plan file. Free text in any other position must still raise a validation error.
-   **Format:**
    ``````markdown
    ### `EDIT`
    - **File Path:** [prompts/architect.md](/prompts/architect.md)
    - **Match All:** `true`
    - **Description:** Update the output formatting instructions.

    #### `FIND:`
    `````xml
    A unique snippet of text, which might include ``` backticks, to be replaced.
    `````
    #### `REPLACE:`
    `````xml
    The new content.
    `````

    #### `FIND:`
    ````xml
    Another snippet to replace.
    ````
    #### `REPLACE:`
    ````xml
    Its corresponding new content.
    ````
    ``````
-   **Parsing Rules:**
    1.  Extract `File Path`, `Description`, and the optional `Match All` (boolean `true`/`false`) from the metadata list.
    2.  The parser looks for sequential pairs of `#### `FIND:`` and `#### `REPLACE:`` headings. The backticks are conventional: the parser matches on the rendered heading text, so the colon matters and the backticks do not. The content for each is the fenced code block that immediately follows the heading.
    3.  **Surgical Changes:** An `EDIT` action must contain at least one `FIND`/`REPLACE` pair. Full-file overwrites are strictly forbidden.
    4.  **Multi-Instance Replacement:** If `Match All: true` is specified, the system will replace *all* occurrences of the `FIND` block within the target file that meet the similarity threshold.

#### `EXECUTE`

-   **Purpose:** Executes a shell command.
-   **Format:**
    `````markdown
    ### `EXECUTE`
    - **Description:** Start the dev server in the background.
    - **Expected Outcome:** The server starts successfully and returns a PID.
    - **Allow Failure:** `false`
    - **Background:** `true`
    - **Timeout:** `120`
    ````shell
    npm start
    ````
    `````
-   **Parsing Rules & Behavior:**
    1.  **Chaining Allowed:** The code block may contain multiple commands linked by shell operators (`&&`, `||`, `;`, `|`, `&`).
    2.  **Directives Allowed:** Environment preparation commands like `cd` or `export` are allowed directly in the command block.
    3.  **Failure Control:** The `Allow Failure` parameter (boolean `true`/`false`) determines if execution continues after a non-zero exit code. It defaults to `false`.
    4.  **Stateless Execution:** Each `EXECUTE` action runs in an isolated environment. Directory or environment changes do not persist between separate `EXECUTE` blocks.
    5.  **Background Execution:** The optional `Background` parameter (boolean `true`/`false`) allows a command to run asynchronously. The CLI will immediately return success with the new Process ID (PID) so the AI can manage the lifecycle in later turns.
    6.  **Timeout Override:** The optional `Timeout` parameter (integer) overrides the global default execution timeout (in seconds) for commands that are intentionally slow but require synchronous output capture.
    7.  **Parameter Extraction:** The parser extracts `Description`, `Expected Outcome`, `Allow Failure` (optional), `Background` (optional), and `Timeout` (optional) from the metadata list.

#### `RESEARCH`

-   **Purpose:** Performs multiple, distinct web searches. The results contain the URL, Page Title, and description. `READ` must be used on individual URLs to retrieve full content.
-   **Format:**
    `````markdown
    ### `RESEARCH`
    - **Description:** Find libraries for parsing Markdown and providing syntax highlighting.
    ````text
    javascript markdown parser library
    ````
    ````text
    best python markdown to html
    prism.js cdn link
    ````
    `````
-   **Parsing Rules:**
    1.  Extract `Description`.
    2.  The parser iterates through every fenced code block.
    3.  Each block is split into individual lines. Each non-empty line (stripped of leading/trailing whitespace) is treated as a separate, individual query.

#### `MOVE`

-   **Purpose:** Moves or renames a file or directory, and rewrites every live context manifest that referenced the old path.
-   **System Behavior:** A successful `MOVE` replaces the source path with the destination path in the live `turn.context` and `session.context`, so the next turn's context payload resolves the new location. Archived session directories are immutable history and are never rewritten.
-   **Format:**

    `````markdown
    ### `MOVE`
    - **Source:** [docs/notes/old-spec.md](/docs/notes/old-spec.md)
    - **Destination:** [docs/specs/spec.md](/docs/specs/spec.md)
    - **Description:** Promote the draft spec to its final location.
    `````

-   **Parameters:**
    -   `Source`: The root-relative path that must already exist.
    -   `Destination`: The root-relative target path that must not yet exist.
    -   `Description`: A short summary of the action.
-   **Parsing Rules:**
    1.  Extract `Source`, `Destination`, and `Description` from the metadata list. Each path accepts a plain path or a root-relative link `[text](/destination)`.
    2.  The action carries no content code block. A `MOVE` never rewrites bytes; only the path changes.
    3.  Both paths pass the shared path-safety rule: no absolute paths and no `..` traversal.
    4.  A `MOVE` applies to files and directories alike. Renaming is a `MOVE` whose destination shares the source's parent directory.
    5.  Missing parent directories of `Destination` are created, matching the `CREATE` behaviour.

#### `DELETE`

-   **Purpose:** Deletes a file or directory, and removes every live context manifest reference to it.
-   **System Behavior:** A successful `DELETE` removes the path from the live `turn.context` and `session.context`. For a directory, every manifest entry beneath that prefix is removed as well. Archived session directories are immutable history and are never rewritten.
-   **Format:**

    `````markdown
    ### `DELETE`
    - **Path:** [docs/notes/obsolete.md](/docs/notes/obsolete.md)
    - **Recursive:** `true`
    - **Description:** Remove the retired notes.
    `````

-   **Parameters:**
    -   `Path`: The root-relative path that must already exist.
    -   `Recursive` (Optional): Required to delete a directory that is not empty. Defaults to `false`.
    -   `Description`: A short summary of the action.
-   **Parsing Rules:**
    1.  Extract `Path`, the optional `Recursive` flag, and `Description` from the metadata list. `Path` accepts a plain path or a root-relative link `[text](/destination)`.
    2.  Omit `Recursive` to accept the default of `false`.
    3.  The action carries no content code block.
    4.  The path passes the shared path-safety rule: no absolute paths and no `..` traversal.
    5.  A `DELETE` applies to files and directories alike.

#### `## Message` (Communicating Turns)

Used when the agent needs to talk to the user, hand off to another agent, or signal completion.
- Everything following the `## Message` header is treated as raw Markdown content for the recipient (the User).
- **Reference Files:** Included as standard Markdown links within the body of the message (e.g., `[report.md](/path/to/report.md)`).
- **Handoffs:** To hand off to another agent, the message should include the specific CLI instruction for the user to start a new session (e.g., `teddy start -a developer ...`).
-   **Mutual Exclusivity:** A plan cannot contain both `## Action Plan` and `## Message`. Together with the one-plan-per-response rule, a response therefore carries exactly one of the two sections.

#### [Deprecated] `PRUNE`, `PROMPT`, `INVOKE`, `RETURN`

These actions are deprecated. `PRUNE` has been removed to simplify context management. `PROMPT`, `INVOKE`, and `RETURN` are replaced by the structural `## Message` section.

#### Deliberate Exclusions

A capability does not earn an action type merely because a shell command can express it.

-   **Empty directories.** `CREATE` writes files and has no directory form: a bare directory path carries no content, so the mandatory content block would have to become conditional. Directory creation stays an `EXECUTE` action running `mkdir -p`, and the parent directories missing from a `CREATE` path are already created automatically, so a nested file needs no preparation step.

-   **`GREP`.** Searching file contents stays an `EXECUTE` action running `git grep`. Three costs outweigh the convenience. Registration is not local: a new action type must be added to the `ActionType` enum, the parser dispatch map, the factory's Markdown-to-internal map and its port map, the validator registry, the report template, and this document, and a single omission fails either pre-flight or rendering. `git grep` searches only tracked files, so a file created earlier in the same plan is invisible unless `--untracked` is passed. And `git grep` exits `1` when nothing matches, which the dispatcher maps to `FAILURE` and halts the remaining actions, so a zero-match-tolerant search must declare `Allow Failure: true` or append `|| true`. Matched file paths reach the next turn's context through a follow-up `READ`.

### Comprehensive Example Plan

The following is a complete, realistic example of a plan file from start to finish.

`````markdown
# Research and Propose a New "Finisher" Agent Role
- **Status:** Green 🟢
- **Plan Type:** Exploration
- **Agent:** Pathfinder

## Rationale
````
### Summary
The user has requested a new "Finisher" agent role, but the exact responsibilities are undefined. This requires a discovery process before implementation.

### Expectation
The research should yield patterns for release management roles, letting me draft a milestone brief and propose next steps. If the research is inconclusive, I will report back and propose a brainstorming session with the user.

### Progress
Goal: Define and get approval for a new "Finisher" agent.
Reference Files: N/A

- [✓] Phase A: Problem Space (Why)
- [▶] Phase B: Solution Space (What)
- [ ] Phase C: Implementation Space (How)
- [ ] Phase D: Handoff (Who)

### Notes
- [TODO] Draft the milestone brief from the research findings.
- [TODO] Propose the milestone to the user for approval.
````

## Action Plan

### `RESEARCH`
- **Description:** Research existing software development roles and CI/CD pipeline patterns related to finalization and release management.
````text
software development release manager responsibilities
````
````text
gitflow vs trunk-based development final steps
````

---

### `CREATE`
- **File Path:** [docs/project/milestones/01-finisher-agent.md](/docs/project/milestones/01-finisher-agent.md)
- **Description:** Create the initial draft of the milestone for the new "Finisher" agent.
````markdown
# Milestone: The "Finisher" Agent

## 1. Business Goal
To streamline the end-of-task workflow by automating final code/documentation cleanup, versioning, and handoff notifications.

## 2. Technical Requirements
*(This section will be populated after research is complete.)*
````

---

### `EDIT`
- **File Path:** [prompts/pathfinder.md](/prompts/pathfinder.md)
- **Description:** Temporarily add the Finisher agent to the Pathfinder's list of handoff targets.

#### `FIND:`
````xml
<handoff_targets>
  <agent>Architect</agent>
  <agent>Debugger</agent>
</handoff_targets>
````
#### `REPLACE:`
````xml
<handoff_targets>
  <agent>Architect</agent>
  <agent>Debugger</agent>
  <agent>Finisher</agent>
</handoff_targets>
````

`````
