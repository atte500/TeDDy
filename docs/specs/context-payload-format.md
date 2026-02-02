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
# Agent Invocation Payload

## 1. System Information
...

## 2. Project Structure
...

## 3. Memos
...

## 4. Context Summary
...

## 5. Resource Contents
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

### 3.2. Project Structure

A textual representation of the repository's file tree, using simple indentation. This gives the AI a high-level map of the project. The tree generation respects two files:
-   `.gitignore`: The standard git ignore file.
-   `.teddyignore`: A TeDDy-specific file that takes priority and can be used to include files that are excluded in `.gitignore`.

-   **Example:**
    `````markdown
    ## 2. Project Structure
    ````
    docs/
      specs/
        context-payload-format.md
        core-philosophy.md
    packages/
      executor/
        pyproject.toml
    prompts/
      architect.xml
    README.md
    ````
    `````

### 3.3. Memos

The verbatim content of the `.teddy/memos.yaml` file. This section is omitted if the file does not exist.

-   **Example:**
    `````markdown
    ## 3. Memos
    ````
    - All API endpoints must be documented in OpenAPI spec.
    - Use 'pnpm' for all package management.
    ````
    `````

### 3.4. Context Summary

This section provides a scannable summary of all file paths and URLs that make up the AI's context for the turn, broken down by their scope of origin.

-   **Example:**
    `````markdown
    ## 4. Context Summary

    ### Turn
    - [src/main.py](/src/main.py)
    - [tests/test_main.py](/tests/test_main.py)

    ### Session
    - [docs/specs/interactive-session-workflow.md](/docs/specs/interactive-session-workflow.md)

    ### Global
    - [docs/specs/core-philosophy.md](/docs/specs/core-philosophy.md)
    ````
    `````

### 3.5. Resource Contents

The full, verbatim content of every resource (file or URL) listed in the `Context Summary`.

-   **Sourcing & De-duplication:** The content is aggregated in the following order of precedence: `turn` -> `session` -> `global`. If a resource is listed in multiple context files, its content will only be displayed once.
-   **Format:** Each resource's content is preceded by a horizontal rule and a header line identifying it.
-   **Example:**
    `````markdown
    ## 5. Resource Contents

    ---
    **Resource:** `[https://example.com/docs](https://example.com/docs)`
    ````html
    <!doctype html>
    <html>
      <head>
        <title>Example Domain</title>
      </head>
      <body>
        <h1>Example Domain</h1>
        <p>This domain is for use in illustrative examples in documents.</p>
      </body>
    </html>
    ````
    ---
    **Resource:** `[docs/specs/core-philosophy.md](/docs/specs/core-philosophy.md)`
    ````markdown
    # TeDDy CLI: A File-Based Front-End for Agentic Coding
    ... (full file content) ...
    ````
    ---
    `````
