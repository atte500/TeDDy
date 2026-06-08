# Specification: Context Payload Format

## Overview

This document specifies the format for the `input.md` file, which serves as the complete context payload provided to an AI agent at the beginning of a planning phase. The `teddy context` command is responsible for generating this file.

The core principle is the **separation of concerns**:
-   **`report.md`** is a factual, historical log of *what happened* in the previous turn.
-   **`input.md`** is the complete, forward-looking worldview for the AI, detailing *the current state of the world* for the upcoming turn.

## Guiding Principles

-   **Markdown-First:** The payload is a valid Markdown document, ensuring it is both human-readable and easily parsable by an LLM.
-   **Structured & Scannable:** The payload uses clear Markdown headings to delineate sections, allowing an AI to easily locate specific pieces of information.
-   **Explicit Sourcing:** The origin of every resource in the context is explicitly stated to avoid ambiguity.
-   **Single Source of Truth:** This payload represents the complete "worldview" for the AI for a given turn.

## Payload Structure (`input.md`)

The payload is a single Markdown document with the following top-level sections.

```markdown
# Project Context

## System Information
...

## Session History (Session Mode only)
...

## Git Status
...

## Project Structure
...

## Resource Contents
...
```

---

### System Information

A simple key-value list of essential environment details, giving the AI awareness of its operating environment.

-   **Example:**
    ```markdown
    ## System Information
    - **CWD:** /Users/developer/projects/TeDDy
    - **OS:** Darwin 25.2.0
    - **Shell:** /bin/zsh
    ```

### Session History

In Stateful (Interactive) Session Mode, the stateful conversation history files (e.g. `initial_request.md`, turn plans, and execution reports under `.teddy/sessions/`) are completely isolated and filtered out of standard `## Resource Contents`.

Instead, they are appended in chronological order under a dedicated `## Session History` section using clean, human-readable turn headers (e.g. `### Initial Request`, `### Turn 1: Plan`, `### Turn 1: Execution Report`) with all raw directory paths stripped out to keep the prompt concise and structured.

-   **Example:**
    `````markdown
    ## Session History

    ### Initial Request
    ````markdown
    Implement user login module.
    ````

    ### Turn 1: Plan
    ````markdown
    We will create the login route in `src/auth.py`.
    ````

    ### Turn 1: Execution Report
    ````markdown
    Successfully created auth module and passed unit tests.
    ````
    `````

### Git Status

A concise view of the current working tree status (`git status -s`). This gives the AI immediate visibility into which files are staged, modified, or untracked. If the repository is clean, it displays a descriptive message.

-   **Example:**
    ```markdown
    ## Git Status
    nothing to commit, working tree clean
    ```

### Project Structure

A textual representation of the repository's file tree, using simple indentation. This gives the AI a high-level map of the project. The tree generation respects two files:
-   `.gitignore`: The standard git ignore file.
-   `.teddyignore`: A TeDDy-specific file that takes priority and can be used to include files that are excluded in `.gitignore`.

-   **Example:**
    `````markdown
    ## Project Structure
    ```
    README.md
    docs
    prompts
    pyproject.toml
    src

    ./docs:
    specs

    ./docs/specs:
    context-payload-format.md
    core-philosophy.md

    ./prompts:
    architect.xml

    ./src:
    teddy_executor

    ./src/teddy_executor:
    main.py
    ```
    `````

### Resource Contents

The full, verbatim content of every resource (file or URL) included in the context.

-   **Format:** Each resource's content is preceded by a horizontal rule and a header line identifying it.
-   **Safety:** Resource contents are enclosed in dynamic code fences (e.g., ```` or ````) that are at least one backtick longer than any existing fence within the content to prevent formatting collisions.
-   **Example:**
    `````markdown
    ## Resource Contents

    ---
    ### [docs/project/specs/core-philosophy.md](/docs/project/specs/core-philosophy.md)
    ````markdown
    # TeDDy CLI: A File-Based Front-End for Agentic Coding
    ... (full file content) ...
    ````
    `````
