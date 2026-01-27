# New Plan Format Specs

## 1. Core Principles

This format is designed to be a perfectly readable Markdown document first, and a machine-parseable plan second.

1.  **Markdown-First:** The document uses standard Markdown headings (`#`, `##`, `###`) to create a readable structure. The layout should feel natural to anyone familiar with Markdown.
2.  **Single Source of Truth (SoT):** All data and metadata are written once directly in the visible Markdown content. There is no hidden or duplicated data.
3.  **Hierarchical Structure:** The plan is a hierarchy of components. The parser should walk the Markdown AST, and the content of any given heading level contains all sub-levels. For example, the `## Action Plan` section contains all the individual action blocks defined by `###` headings.

## 2. Overall Document Structure

A plan is a single Markdown file with the following top-level structure:

```markdown
# [Descriptive Plan Title]
- **Status:** ...
- **Agent:** ...
...

## Context Vault
...

## Rationale
...

## Memos
... (Optional: Contains a list of memory changes)

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
    - **Goal:** Create the initial documentation for the new plan format.
    ```
-   **Parsing Rules:** The plan's title is the content of the `#` heading. The metadata is the bulleted list that immediately follows it. The parser should treat this list as key-value pairs.

### 4.2. Context Vault

-   **Purpose:** Lists the file paths relevant to the current task.
-   **Format:**
    ```markdown
    ## Context Vault
    ````
    docs/specs/plan-format.md
    prompts/architect.xml
    ````
    ```
-   **Parsing Rules:** The parser should extract the content of the code block and treat each line as a separate file path.

### 4.3. Memos (Optional)

-   **Purpose:** Lists the proposed changes (creations and deletions) to the agent's long-term memory.
-   **Format:**
    ```markdown
    ## Memos
    - [+] A new fact to remember.
    - [+] Another new fact.
    - [-] An old fact that is no longer true.
    ```
-   **Parsing Rules:** The parser should treat this as a list of change requests. Each list item must start with either `[+]` for creation or `[-]` for deletion. The text following the marker is the content of the memo.

### 4.4. Rationale

-   **Purpose:** Contains the agent's reasoning, state, and thought process.
-   **Format:**
    ```markdown
    ## Rationale
    1. **Observation:** Free-form Markdown content...
    2. **Analysis:** More free-form Markdown...
    ```
-   **Parsing Rules:** The content is free-form Markdown and is primarily for human consumption.

## 5. Action Blocks

All actions are located under the `## Action Plan` heading. Each action is defined by its own `###` heading.

### 5.1. `CREATE`

-   **Purpose:** Creates a new file.
-   **Format:**
    `````markdown
    ### `CREATE`
    - **File Path:** [docs/specs/plan-format.md](/docs/specs/plan-format.md)
    - **Description:** Create the initial specification document.
    ````markdown
    # Specification: The Pure Markdown Plan Format
    ... file content ...
    ````
    `````
-   **Parsing Rules:**
    1.  Extract `File Path` and `Description` from the metadata list.
    2.  The content for the new file is the entire content of the first fenced code block.

### 5.2. `READ`

-   **Purpose:** Reads a file or URL.
-   **Format:**
    ```markdown
    ### `READ`
    - **Resource:** [docs/ARCHITECTURE.md](/docs/ARCHITECTURE.md)
    - **Description:** Read the current architectural conventions.
    ```
-   **Parsing Rules:** Extract `Resource` and `Description` from the metadata list.

### 5.3. `EDIT`

-   **Purpose:** Edits an existing file.
-   **Format:**
    `````markdown
    ### `EDIT`
    - **File Path:** [prompts/architect.xml](/prompts/architect.xml)
    - **Description:** Update the output formatting instructions.

    `FIND:`
    ````xml
    A unique snippet of text to be replaced.
    ````
    `REPLACE:`
    ````xml
    The new content.
    ````

    `FIND:`
    ````xml
    Another snippet to replace.
    ````
    `REPLACE:`
    ````xml
    Its corresponding new content.
    ````
    `````
-   **Parsing Rules:**
    1.  Extract `File Path` and `Description`.
    2.  The parser looks for sequential pairs of `FIND:` and `REPLACE:` blocks. Each block is a standard fenced code block.
    3.  **Edge Case (Full Overwrite):** If the action contains only a single `REPLACE:` block, the entire file is overwritten.

### 5.4. `EXECUTE`

-   **Purpose:** Executes a shell command.
-   **Format:**
    `````markdown
    ### `EXECUTE`
    - **Description:** Verify the new file was created.
    - **Expected Outcome:** The output will list `plan-format.md`.
    ````shell
    ls -l docs/specs/
    ````
    `````
-   **Parsing Rules:**
    1.  Extract `Description` and `Expected Outcome`.
    2.  The command to execute is the entire content of the first fenced code block.

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
    ````
    ````text
    prism.js cdn link
    ````
    `````
-   **Parsing Rules:**
    1.  Extract `Description`.
    2.  The parser should treat every fenced code block as a separate query.

### 5.6. `CHAT_WITH_USER`

-   **Purpose:** Communicates with the user.
-   **Format:**
    ```markdown
    ### `CHAT_WITH_USER`
    I have created a draft brief at `docs/briefs/01-finisher-agent-brief.md` and will now begin my research.

    This is a standard checkpoint to ensure we are aligned before I proceed with the research phase. Does this initial direction meet with your approval?
    ```
-   **Parsing Rules:** The content for the chat message is all the free-form markdown content under the `### CHAT_WITH_USER` heading.

### 5.7. `INVOKE`

-   **Purpose:** Hands off control to another agent.
-   **Format:**
    ```markdown
    ### `INVOKE`
    - **Agent:** Architect

    Handoff to the Architect.

    The brief is complete and located at `docs/briefs/01-finisher-agent-brief.md`. Please proceed with creating a detailed technical design and implementation plan.
    ```
-   **Parsing Rules:**
    1. Extract the target `Agent` from the metadata list.
    2. The content for the invocation message is all the free-form markdown content that follows the metadata list.

## 6. Comprehensive Example Plan

The following is a complete, realistic example of a plan file from start to finish.

`````markdown
# Research and Propose a New "Finisher" Agent Role
- **Status:** Green 🟢
- **Plan Type:** Exploration
- **Agent:** Pathfinder
- **Goal:** Research the concept of a "Finisher" agent and create a formal brief.

## Context Vault
````
docs/briefs/01-finisher-agent-brief.md
prompts/pathfinder.xml
````

## Rationale
1. **Observation:** The user has requested a new "Finisher" agent role responsible for final cleanup, versioning, and handoff tasks. The exact responsibilities are not yet defined.
2. **Analysis:** This requires a discovery process. I need to research existing patterns for this type of role and then synthesize the findings into a concrete proposal (a brief) for the user to approve. This follows the standard Pathfinder workflow of Why -> What -> How.
3. **Next Step**
   - **Current Focus:** Solution Space Exploration
   - **Justification:** I need to gather external information before I can propose a solution. The first step is to perform web research.

## Action Plan

### `RESEARCH`
- **Description:** Research existing software development roles and CI/CD pipeline patterns related to finalization and release management.
````text
software development release manager responsibilities
````
````text
gitflow vs trunk-based development final steps
````

### `CREATE`
- **File Path:** [docs/briefs/01-finisher-agent-brief.md](/docs/briefs/01-finisher-agent-brief.md)
- **Description:** Create the initial draft of the brief for the new "Finisher" agent.
````markdown
# Brief: The "Finisher" Agent

## 1. Business Goal
To streamline the end-of-task workflow by automating final code/documentation cleanup, versioning, and handoff notifications.

## 2. Technical Requirements
*(This section will be populated after research is complete.)*
````

### `EDIT`
- **File Path:** [prompts/pathfinder.xml](/prompts/pathfinder.xml)
- **Description:** Temporarily add the Finisher agent to the Pathfinder's list of handoff targets.

`FIND:`
````xml
<handoff_targets>
  <agent>Architect</agent>
  <agent>Debugger</agent>
</handoff_targets>
````
`REPLACE:`
````xml
<handoff_targets>
  <agent>Architect</agent>
  <agent>Debugger</agent>
  <agent>Finisher</agent>
</handoff_targets>
````

### `CHAT_WITH_USER`
I have created a draft brief at `docs/briefs/01-finisher-agent-brief.md` and will now begin my research. I will report back with my findings and a more detailed proposal for the brief.

Does this initial direction meet with your approval?

### `INVOKE`
- **Agent:** Architect

Handoff to Architect to begin implementation of the approved brief.
`````
