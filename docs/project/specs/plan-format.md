# New Plan Format Specs

## 1. Core Principles

This format is designed to be a perfectly readable Markdown document first, and a machine-parseable plan second.

1.  **Markdown-First:** The document uses standard Markdown headings (`#`, `##`, `###`) to create a readable structure. The layout should feel natural to anyone familiar with Markdown.
2.  **Single Source of Truth (SoT):** All data and metadata are written once directly in the visible Markdown content. There is no hidden or duplicated data.
3.  **Hierarchical Structure:** The plan is a hierarchy of components. The parser should walk the Markdown AST, and the content of any given heading level contains all sub-levels. For example, the `## Action Plan` section contains all the individual action blocks defined by `###` headings.

## 2. Overall Document Structure

### 2.1. Code Block Nesting

A core principle of this format is that it must reliably handle nested code blocks, which is a common source of errors in LLM-generated Markdown.

-   **The Problem:** If a code block's content contains a sequence of backticks (e.g., ` ``` `) that is the same length as the enclosing fence, the Markdown becomes invalid and cannot be parsed correctly.
-   **The Rule (Primary Defense):** When creating a fenced code block, the fence **must** use a number of backticks that is strictly greater than the longest sequence of backticks found anywhere inside the content. This instruction is the primary defense against parsing errors.
-   **System Support (Validation & Self-Correction):** To guarantee robustness, the system includes a pre-flight validation check that is **run automatically** by the `teddy execute` command. Before any plan is presented to the user for approval, the system first ensures it is well-formed and parsable. If parsing fails (e.g., due to an ambiguous code fence), it triggers the **Automated Re-plan Loop** which instructs the AI to correct its own formatting error. See the [Plan Validation & Automated Re-planning](/docs/project/specs/interactive-session-workflow.md#8-plan-validation--automated-re-planning) section for full details.

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

## 3. File Linking Conventions

To ensure links work correctly in local previews (like VSCode) while referencing the project root, a specific syntax must be used.

-   **Root-Relative Links (Required):** All links to files within the project must be relative to the project's root directory.
    -   **Syntax:** `[path/from/root](/path/from/root)`
    -   **Explanation:** The link text (in square brackets) is the path from the root *without* a leading slash. The link destination (in round brackets) is the same path *with* a leading slash.
    -   **Example:** `[docs/ARCHITECTURE.md](/docs/ARCHITECTURE.md)`
    -   **Behavior:** This specific structure ensures that the link text is displayed cleanly while the link itself resolves correctly from the project root in the previewer.

## 4. Core Component Blocks

### 4.1. Plan Header

-   **Purpose:** Contains the plan's title and high-level metadata. It must be the first and only Level 1 (`#`) heading in the document.
-   **Format:**
    ```markdown
    # A Descriptive Plan Title
    - **Status:** Green 🟢
    - **Plan Type:** Implementation
    - **Agent:** Pathfinder
    ```
-   **Parsing Rules:** The plan's title is the content of the `#` heading. The metadata is the bulleted list that immediately follows it. The parser should treat this list as key-value pairs.

### 4.2. Rationale

-   **Purpose:** Contains the agent's reasoning, state, and thought process. It acts as a **cognitive forcing function** to ensure every plan is grounded, deliberate, and strategic.
-   **Format:** The `Rationale` block is a plain text code block that **must** contain four distinct sections, each with a `###` heading, in the following order: `### 1. Synthesis`, `### 2. Justification`, `### 3. Expected Outcome`, and `4. State Dashboard`.

    `````markdown
    ## Rationale
    ````text
    ### 1. Synthesis
    [A review of the previous turn's outcome and what it means for the mission.]

    ### 2. Justification
    [A direct narrative that synthesizes the current situation and explains how the proposed plan is the next logical step according to all applicable principles of the agent's core methodology.]

    ### 3. Expected Outcome
    [A clear statement of what will happen in both success and failure scenarios, including the `Plan Type` of the subsequent plan.]

    ### 4. State Dashboard
    [The agent's complete, multi-step workflow status (e.g., Pathfinder's Log).]
    ````
    `````
-   **Parsing Rules:** The content is the raw text within the fenced code block and is primarily for human consumption and agent self-correction. The outer fence for the `Rationale` block must follow the **Code Block Nesting** rule.

## 5. Action Blocks

All actions are located under the `## Action Plan` heading. Each action is defined by its own `###` heading.

### 5.1. `CREATE`

-   **Purpose:** Creates a new file.
-   **Format:**
    `````markdown
    ### `CREATE`
    - **File Path:** [docs/project/specs/plan-format.md](/docs/project/specs/plan-format.md)
    - **Overwrite:** true
    - **Description:** Create the initial specification document.
    ````markdown
    # Specification: The Pure Markdown Plan Format
    ... file content ...
    ````
    `````
-   **Parameters:**
    -   `File Path`: The root-relative path to the file.
    -   `Overwrite` (Optional): If `true`, allows replacing an existing file. Use with extreme caution.
    -   `Description`: A short summary of the action.
-   **Parsing Rules:**
    1.  Extract `File Path`, `Overwrite`, and `Description` from the metadata list.
    2.  The content for the new file is the entire content of the first fenced code block.

### 5.2. `READ`

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

### 5.3. `EDIT`

-   **Purpose:** Edits an existing file. It is strongly preferred to make surgical changes by including multiple, small, sequential `FIND`/`REPLACE` pairs in a single action rather than one large replacement.
-   **Format:**
    ``````markdown
    ### `EDIT`
    - **File Path:** [prompts/architect.xml](/prompts/architect.xml)
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
    1.  Extract `File Path` and `Description`.
    2.  The parser looks for sequential pairs of `#### `FIND:`` and `#### `REPLACE:`` headings. The keywords **must** be enclosed in backticks. The content for each is the fenced code block that immediately follows the heading.
    3.  **Surgical Changes:** An `EDIT` action must contain at least one `FIND`/`REPLACE` pair. Full-file overwrites are strictly forbidden.

### 5.4. `EXECUTE`

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
    3.  **Failure Control:** The `Allow Failure` parameter (boolean `true`/`false`) determines if execution continues after a non-zero exit code. It defaults to `false`. The value MUST be enclosed in backticks.
    4.  **Stateless Execution:** Each `EXECUTE` action runs in an isolated environment. Directory or environment changes do not persist between separate `EXECUTE` blocks.
    5.  **Background Execution:** The optional `Background` parameter (boolean `true`/`false`) allows a command to run asynchronously. The CLI will immediately return success with the new Process ID (PID) so the AI can manage the lifecycle in later turns. The value MUST be enclosed in backticks.
    6.  **Timeout Override:** The optional `Timeout` parameter (integer) overrides the global default execution timeout (in seconds) for commands that are intentionally slow but require synchronous output capture.
    7.  **Parameter Extraction:** The parser extracts `Description`, `Expected Outcome`, `Allow Failure` (optional), `Background` (optional), and `Timeout` (optional) from the metadata list.

### 5.5. `RESEARCH`

-   **Purpose:** Performs multiple, distinct web searches.
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

### 5.6. `PROMPT`

-   **Purpose:** Communicates with the user. **CRITICAL RULE:** This action MUST be the ONLY action in the plan. It cannot be combined with any other actions (e.g., CREATE, EDIT, EXECUTE).
-   **Format:**
    ```markdown
    ### `PROMPT`
    - **Reference Files:**
      [path/to/file.ext](/path/to/file.ext)

    I have created a new milestone at `docs/project/milestones/01-finisher-agent.md` and will now begin my research.

    This is a standard checkpoint to ensure we are aligned before I proceed with the research phase. Does this initial direction meet with your approval?
    ```
-   **Parsing Rules:** The content for the message is all the free-form markdown content under the `### PROMPT` heading. The parser does not explicitly separate metadata from the message; it is treated as a single block of text.

### 5.7. `INVOKE`

-   **Purpose:** Hands off control to another agent, resetting the context for a new task. **CRITICAL RULE:** This action MUST be the ONLY action in the plan. It cannot be combined with any other actions.
-   **Format:**
    ```markdown
    ### `INVOKE`
    - **Agent:** Architect
    - **Description:** The feature discovery is complete and the problem is validated.
    - **Reference Files:** (Optional)
    [docs/project/milestones/new-feature.md](/docs/project/milestones/new-feature.md)
    ```
-   **Parsing Rules:**
    1.  Extract the target `Agent` and the `Description` from the metadata list.
    2.  Extract the optional list of `Reference Files`. These should be formatted as a multi-line list of root-relative links without leading bullets. The link text should be the full path from the project root.
    3.  The `Description` serves as the short explanation of the handoff. Free-form text following the metadata list is forbidden.

### 5.8. `RETURN`

-   **Purpose:** Returns control to the calling agent after a specialist sub-task is complete. **CRITICAL RULE:** This action MUST be the ONLY action in the plan. It cannot be combined with any other actions.
-   **Format:**
    ```markdown
    ### `RETURN`
    - **Description:** The implementation and testing of the vertical slice are complete.
    - **Reference Files:** (Optional)
    [docs/project/debugging/rca/the-bug.md](/docs/project/debugging/rca/the-bug.md)
    [spikes/fix-script.sh](/spikes/fix-script.sh)
    ```
-   **Parsing Rules:**
    1.  Extract the `Description` from the metadata list.
    2.  Extract the optional list of `Reference Files`. These should be formatted as a multi-line list of root-relative links without leading bullets. The link text should be the full path from the project root.
    3.  The `Description` serves as the short explanation of the task completion. Free-form text following the metadata list is forbidden.

### 5.9. `PRUNE`

-   **Purpose:** Removes a resource from the agent's working context for subsequent turns. This is used to prevent context clutter.
-   **Format:**
    ````markdown
    ### `PRUNE`
    -   **Resource:** [docs/project/specs/old-spec.md](/docs/project/specs/old-spec.md)
    -   **File Path:** [docs/project/specs/old-spec.md](/docs/project/specs/old-spec.md)
    -   **Description:** Remove the old specification as it is no longer relevant.
    ````
-   **Parsing Rules:**
    1.  Extract `Resource` or `File Path` and `Description`.
    2.  `File Path` is an alias for local resources and **strictly forbids URLs**.
    3.  The value for either can be a root-relative Markdown link `[text](/destination)`. The parser should use the destination as the path to remove from the context.

## 6. Comprehensive Example Plan

The following is a complete, realistic example of a plan file from start to finish.

`````markdown
# Research and Propose a New "Finisher" Agent Role
- **Status:** Green 🟢
- **Plan Type:** Exploration
- **Agent:** Pathfinder

## Rationale
````
1. Synthesis
The user has requested a new "Finisher" agent role, but the exact responsibilities are undefined. This requires a discovery process before implementation.

2. Justification
This plan adheres to the Pathfinder "Why -> What -> How" workflow. The problem is understood ("Why"), but the solution is not. Therefore, the next logical step is to explore the Solution Space ("What") by gathering external information to inform a proposal.

3. Expected Outcome
The research is expected to yield patterns for release management roles, allowing me to draft a brief. The next plan will be a `Synthesis` plan. If the research yields no clear patterns, the next plan will be a `PROMPT` plan to propose a brainstorming session with the user.

4. State Dashboard
- Overall Goal: Define and get approval for a new "Finisher" agent.
- Phase A: Problem Space (Why): Approved
- Phase B: Solution Space (What): In Progress
- Phase C: Implementation Space (How): Not Started
- Phase D: Handoff (Who): Not Started
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
- **File Path:** [prompts/pathfinder.xml](/prompts/pathfinder.xml)
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

---

### `PROMPT`
I have created a draft milestone at `docs/project/milestones/01-finisher-agent.md` and will now begin my research. I will report back with my findings and a more detailed proposal for the milestone.

Does this initial direction meet with your approval?

---

### `INVOKE`
- **Agent:** Architect
- **Description:** Handoff to Architect to begin implementation of the approved milestone.
`````
