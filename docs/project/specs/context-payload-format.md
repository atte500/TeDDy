# Spec: Context Payload Format

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
-   **Byte-Stable Prefix:** The sections are ordered so the session's stable documents and its accumulated history sit ahead of everything that changes between turns. Two consecutive payloads then share a byte-identical prefix, which a provider serves from its prompt cache instead of reprocessing.

## Technical Specifications

The payload is a single Markdown document with the following top-level sections, in this order.

```markdown
# Project Context

## System Information
...

## Session Resources (Session Mode only)
...

## Session History (Session Mode only)
...

## Git Status
...

## Project Structure
...

## Resource Contents
...

## Runtime
...
```

The order is load-bearing. A provider's prefix cache serves only the leading bytes that match an earlier request, so the first difference between two consecutive payloads decides how much of the payload is free. The session's own documents come first, then its history, which grows by appending; the sections that change every turn follow, and `## Runtime` closes the document because it holds the values that always change.

Session-mode sections (`## Session Resources` and `## Session History`) render only when a session root is in scope. A session-agnostic `teddy context` export carries neither and keeps a single `## Resource Contents` section for every resource, the shape the CHOP workflow expects.

---

### System Information

A simple key-value list of the environment details that stay constant for the whole session, giving the AI awareness of its operating environment without disturbing the byte-stable prefix.

The list closes with a static pointer row naming the `## Runtime` section, so the agent still finds the date, time, and turn number after they move to the payload tail. The row carries no values, so it never varies between turns.

-   **Rows, in order:** `CWD`, `OS`, `Shell`, then the `Runtime` pointer row.
-   **Example:**
    ```markdown
    ## System Information
    - **CWD:** /Users/developer/projects/TeDDy
    - **OS:** Darwin 25.2.0
    - **Shell:** /bin/zsh
    - **Runtime:** Current Date, Current Time, and Current Turn appear under the final `## Runtime` section.
    ```

### Session Resources

In session mode, the files the session holds across turns render here, directly behind the header. These are the payload's most rewarding cacheable bytes: they usually change little between turns, so a provider serves them from cache instead of reprocessing them.

A file qualifies when it is listed in a scope other than `Turn` and is not part of this session's own history.

-   **Ordering:** Files render in `session.context` declaration order, so that manifest's order is the user's knob: a document that rarely changes stays inside the cached prefix as long as the documents above it do too.
-   **Precedence:** A path listed in both the session and turn scopes renders here only, so the payload never carries the same content twice.
-   **Own history stays out:** A session-scoped path that is this session's own history renders under `## Session History` instead, because that section pins chronological order and its `### Initial Request` / `### Turn N` headers.
-   **Omission:** The section is omitted entirely when no file qualifies, when the session context holds only history, or when no session root is in scope. An empty heading is indistinguishable from an omitted one, so it is never rendered.
-   **Format:** Each file is preceded by a horizontal rule and a header line, and its content is enclosed in a dynamic fence, exactly as in `## Resource Contents`.
-   **Example:**
    `````markdown
    ## Session Resources

    ---
    ### [docs/project/PROJECT.md](/docs/project/PROJECT.md)
    ````markdown
    # Project Dashboard: TeDDy
    ... (full file content) ...
    ````
    `````

### Session History

In Stateful (Interactive) Session Mode, the stateful conversation history files (e.g. `initial_request.md`, turn plans, and execution reports under `.teddy/sessions/`) are completely isolated and filtered out of standard `## Resource Contents`.

Instead, they are appended in chronological order under a dedicated `## Session History` section using clean, human-readable turn headers (e.g. `### Initial Request`, `### Turn 1: Plan`, `### Turn 1: Execution Report`) with all raw directory paths stripped out to keep the prompt concise and structured.

The section follows `## Session Resources`, so both stable parts of the session sit directly behind the header and form one growing cached prefix. Only the session's own root belongs here: a file read from another session is a resource, not our history.

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

A concise, deterministic view of the working tree (`git status --porcelain -b`). The first line carries the branch name, its upstream, and ahead/behind counts. Each following line uses the two-column porcelain format, where the first column reports the index state and the second column reports the worktree state.

The body sits inside a fenced block. The porcelain header starts with `##`, so without the fence it would render as a sibling heading to the Git Status section. The fence also preserves the significant leading column of worktree-only changes.

The porcelain form ignores user color and prefix configuration, so the payload stays stable across developer environments. A clean repository yields only the branch header. When the directory is not a Git repository, the section stays empty.

-   **Example:**
    ````markdown
    ## Git Status
    ```
    ## feature/auth...origin/feature/auth [ahead 1]
    M  docs/project/PROJECT.md
     M src/teddy_executor/core/services/context_service.py
    ?? tests/test_new_feature.py
    ```
    ````

-   **Clean example:**
    ````markdown
    ## Git Status
    ```
    ## main...origin/main
    ```
    ````

### Project Structure

A textual representation of the repository's file tree, using simple indentation. This gives the AI a high-level map of the project. The tree generation respects two files:
-   `.gitignore`: The standard git ignore file.
-   `.teddyignore`: A TeDDy-specific file that takes priority and can be used to include files that are excluded in `.gitignore`.

The tree honors two limits. `context.max_depth` bounds nesting, and `context.max_children` bounds visible entries per subdirectory. A directory at or beyond the depth limit, or holding more visible entries than the `max_children` cap, renders one notice `[X folders, Y files]` instead of its children. Its descendant sections are omitted, because names without their parent folder cannot be mapped. The counts cover visible immediate children only, after ignore rules. A depth of zero collapses the section to one notice for the project root and lists no child entry.

An unreadable directory renders `[unreadable]`, because a failed scan must not present a count. A directory with no visible child renders no section, because an empty directory is not an omission. The project root listing is exempt from the `max_children` cap, because it is the only place where a top-level file is named. The depth limit still applies first, so a depth of zero withholds the root.

The notices carry no explanation, so the section states both limits once in an italic subtitle placed between the heading and the fence.

-   **Example:**
    `````markdown
    ## Project Structure
    *Tree capped at depth 3 and 20 entries per subdirectory: truncated directories show entry counts only.*
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
    architect.md

    ./src:
    teddy_executor

    ./src/teddy_executor:
    main.py

    ./src/teddy_executor/core:
    [2 folders, 0 files]

    ./tests/suites/acceptance:
    [0 folders, 82 files]
    ```
    `````

### Resource Contents

The content of every resource (file or URL) that is neither hoisted into `## Session Resources` nor part of `## Session History`. A text resource renders verbatim; a PDF resource renders as its extracted text layer.

In session mode this is the turn-scoped working set: the files the current turn pulled in. A session-agnostic `teddy context` export has no session sections, so every resource renders here.

-   **Format:** Each resource's content is preceded by a horizontal rule and a header line identifying it.
-   **PDF Resources:** A local path ending in `.pdf`, matched case-insensitively with any query string or fragment ignored, is read as bytes and embedded as the text layer extracted through `IPdfExtractor`, capped by `read.max_lines`. A missing file renders the same `--- FILE NOT FOUND ---` marker as a text resource; an extraction failure fails the assembly with a `PdfExtractionError` naming the path.
-   **Safety:** Resource contents are enclosed in dynamic code fences (e.g., ```` or ````) that are at least one backtick longer than any existing fence within the content to prevent formatting collisions.
-   **Omission:** The section is omitted when no resource remains for it.
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

### Runtime

The payload's final section. It holds exactly the three key-value rows that change on every turn: `Current Date`, `Current Time`, and `Current Turn`.

Keeping them here holds per-turn values out of the byte-stable prefix. Since the three rows are its only content, the pointer row in `## System Information` stays a truthful single-line signpost. The section renders in every mode, including a session-agnostic `teddy context` export, because those values exist regardless of session scope.

-   **Rows, in order:** `Current Date`, `Current Time`, `Current Turn`.
-   **Example:**
    ```markdown
    ## Runtime
    - **Current Date:** 2026-03-26
    - **Current Time:** 16:50:00
    - **Current Turn:** 02
    ```
