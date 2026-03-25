# Specification: Context Payload Format

## 1. Overview

This document specifies the format for the `input.md` file, which serves as the complete context payload provided to an AI agent at the beginning of a planning phase. The `teddy context` command is responsible for generating this file.

The core principle is the **separation of concerns**:
-   **`report.md`** is a factual, historical log of *what happened* in the previous turn.
-   **`input.md`** is the complete, forward-looking worldview for the AI, detailing *the current state of the world* for the upcoming turn.

## 2. Guiding Principles

-   **Markdown-First:** The payload is a valid Markdown document, ensuring it is both human-readable and easily parsable by an LLM.
-   **Structured & Scannable:** The payload uses clear Markdown headings to delineate sections, allowing an AI to easily locate specific pieces of information.
-   **Explicit Sourcing:** The origin of every resource in the context is explicitly stated to avoid ambiguity.
-   **Single Source of Truth:** This payload represents the complete "worldview" for the AI for a given turn.

## 3. Payload Structure (`input.md`)

The payload is a single Markdown document with the following top-level sections.

```markdown
# Project Context

## 1. System Information
...

## 2. Git Status
...

## 3. Project Structure
...

## 4. Resource Contents
...
```

---

### 3.1. System Information

A simple key-value list of essential environment details, giving the AI awareness of its operating environment.

-   **Example:**
    ```markdown
    ## 1. System Information
    - **CWD:** /Users/developer/projects/TeDDy
    - **OS:** Darwin 25.2.0
    - **Shell:** /bin/zsh
    ```

### 3.2. Git Status

A concise view of the current working tree status (`git status -s`). This gives the AI immediate visibility into which files are staged, modified, or untracked. If the repository is clean, it displays a descriptive message.

-   **Example:**
    ```markdown
    ## 2. Git Status
    nothing to commit, working tree clean
    ```

### 3.3. Project Structure

A textual representation of the repository's file tree, using simple indentation. This gives the AI a high-level map of the project. The tree generation respects two files:
-   `.gitignore`: The standard git ignore file.
-   `.teddyignore`: A TeDDy-specific file that takes priority and can be used to include files that are excluded in `.gitignore`.

-   **Example:**
    `````markdown
    ## 3. Project Structure
    ```
    docs/
      specs/
        context-payload-format.md
        core-philosophy.md
    src/
      teddy_executor/
        main.py
    prompts/
      architect.xml
    pyproject.toml
    README.md
    ```
    `````

### 3.4. Resource Contents

The full, verbatim content of every resource (file or URL) included in the context.

-   **Format:** Each resource's content is preceded by a horizontal rule and a header line identifying it.
-   **Safety:** Resource contents are enclosed in dynamic code fences (e.g., ```` or ````) that are at least one backtick longer than any existing fence within the content to prevent formatting collisions.
-   **Example:**
    `````markdown
    ## 4. Resource Contents

    ---
    ### [docs/project/specs/core-philosophy.md](/docs/project/specs/core-philosophy.md)
    ````markdown
    # TeDDy CLI: A File-Based Front-End for Agentic Coding
    ... (full file content) ...
    ````
    `````
