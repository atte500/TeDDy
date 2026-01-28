# Context Payload Format Specification

## 1. Overview

This document specifies the format for the complete context payload provided to an AI agent at the beginning of a planning phase (e.g., via `teddy plan` or `teddy resume`). The format is designed to be a comprehensive, structured, and unambiguous Markdown document that gives the AI all necessary information to reason about the project and generate a plan.

## 2. Guiding Principles

- **Structured & Scannable:** The payload uses clear Markdown headings to delineate sections, allowing an AI to easily parse and locate specific pieces of information.
- **Explicit Sourcing:** The origin of every piece of context (especially files) is explicitly stated to avoid ambiguity.
- **Single Source of Truth:** This payload represents the complete "worldview" for the AI for a given turn.

## 3. Payload Structure

The payload is a single Markdown document with the following top-level sections.

```markdown
# Agent Invocation Payload

## 1. System Information
...

## 2. Project Structure
...

## 3. Memos
...

## 4. Active Context
...

## 5. File Contents
...
```

---

### 3.1. System Information

A simple key-value list of essential environment details.

- **Example:**
  ```markdown
  ## 1. System Information
  - **CWD:** /Users/developer/projects/TeDDy
  - **OS:** Darwin 25.2.0
  - **Shell:** /bin/zsh
  ```

### 3.2. Project Structure

A textual representation of the repository's file tree, respecting `.gitignore` and `.teddyignore` rules.

- **Example:**
  `````markdown
  ## 2. Project Structure
  ````
  .
  ├── .teddy/
  │   ├── global.context
  │   ├── memos.yaml
  │   └── sessions/
  ├── docs/
  └── src/
  ````
  `````

### 3.3. Memos

The verbatim content of the `.teddy/memos.yaml` file, providing the AI with global, persistent facts or constraints. It is presented as a simple list inside a code block.

- **Example:**
  `````markdown
  ## 3. Memos
  ````
  - All API endpoints must be documented in OpenAPI spec.
  - Use 'pnpm' for all package management.
  ````
  `````

### 3.4. Active Context

This section lists only the file paths from the current `turn.context`. It represents the set of files the AI can directly influence for the *next* turn by proposing changes in its `Active Context` plan block. It is presented as a simple list inside a code block.

- **Example:**
  `````markdown
  ## 4. Active Context
  ````
  - src/feature_x.py
  - tests/test_feature_x.py
  ````
  `````

### 3.5. File Contents

The full, verbatim content of every file from the combined context (`global`, `session`, and `turn`). Each file's content is clearly delineated.

- **Example:**
  `````markdown
  ## 5. File Contents

  ---
  **File:** `[README.md](/README.md)`
  ````markdown
  # TeDDy: Your Contract-First & Test-Driven Pair-Programmer
  ... (full file content) ...
  ````
  ---
  **File:** `[docs/ARCHITECTURE.md](/docs/ARCHITECTURE.md)`
  ````markdown
  # System Architecture: TeDDy
  ... (full file content) ...
  ````
  ---
  **File:** `[src/main.py](/src/main.py)`
  ````python
  # src/main.py
  ... (full file content) ...
  ````
  `````

## 4. Comprehensive Example

The following is a complete, realistic example of a context payload file from start to finish.

``````markdown
# Agent Invocation Payload

## 1. System Information
- **CWD:** /Users/developer/projects/TeDDy
- **OS:** Darwin 25.2.0
- **Shell:** /bin/zsh

## 2. Project Structure
````
.
├── .teddy/
│   ├── global.context
│   ├── memos.yaml
│   └── sessions/
│       └── 20260124-add-user-auth/
│           ├── session.context
│           └── 01/
│               └── turn.context
├── docs/
│   └── specs/
│       └── interactive-session-workflow.md
└── src/
    └── main.py
````

## 3. Memos
````
- All API endpoints must be documented in OpenAPI spec.
- Use 'pnpm' for all package management.
````

## 4. Active Context
````
- src/main.py
````

## 5. File Contents

---
**File:** `[docs/specs/interactive-session-workflow.md](/docs/specs/interactive-session-workflow.md)`
````markdown
# Interactive session workflow specs

## 1. Overview

This document specifies the design and behavior of the new interactive, file-based session workflow for TeDDy.
... (content truncated for example)
````
---
**File:** `[src/main.py](/src/main.py)`
````python
# src/main.py

import typer

def main():
    print("Hello, world!")

if __name__ == "__main__":
    typer.run(main)
````
``````
