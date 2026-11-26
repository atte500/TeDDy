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

Session-mode sections (`## Session Resources` and `## Session History`) render only when a session root is in scope. A session-agnostic `teddy context` export carries neither and keeps a single `## Resource Contents` section for every resource, the shape the CHOP workflow expects: a `.teddy/sessions/` path supplied to an export is a resource there, never history.

### Measured Basis for the Order

The order above was measured rather than assumed, over consecutive `input.md` pairs of real sessions. Only payloads carrying this layout count: an older payload keeps the per-turn clock rows in its header, which caps every order at the same ~96-byte prefix and makes the comparison meaningless.

-   **Population:** the order comparisons come from the pre-change layout: 40 consecutive pairs across 3 sessions, 11.6 MB of payload, mean payload 289 KB, split as a 39-pair order run and a 40-pair attribution run, one turn of drift because a new turn entered the corpus between runs. The break attribution was re-measured on the shipped layout over 5 sessions of 2026-11-25, 71 pairs, payloads between 60 KB and 110 KB, and every bullet below that names a break mechanism comes from that corpus. The metric counts bytes while providers cache in token blocks, and it tracks the provider's own accounting rather than standing in for it: 65.5% byte share against 61.2% reported cache hits over 30 turns, 75.3% against 76.7% over 9.
-   **Where the prefix ends on the pre-change layout:** in 29 pairs the shared prefix ran to the end of `## Session History`, in 10 it died inside that section because retention front-truncated it, in 1 inside `## Session Resources` because a listed document was edited, and never later. The cached set is therefore exactly `## Session Resources` plus `## Session History` — 60.4% of a mean payload by weight, 67.2% at the median, 27.6% at the tenth percentile.
-   **Where it ends on the shipped layout:** `## Session Resources` breaks the prefix far more often than the pre-change corpus suggested, in 12 of 71 pairs against 1 of 40. The cause is a mutable working document admitted to the session manifest, not an incidental edit: one 30-pair session lost 11 pairs to a slice document and a config-schema document being edited while they were being worked on, and that session would have scored 83.6% instead of 65.5% had those documents stayed byte-identical. The counterfactual assumes zero edits, so it is an upper bound and never a forecast.
-   **History breaks have three kinds:** retention front truncation advances the oldest retained turn, so everything from that header onward is forfeited; mid-section removal deselects a turn from the middle of the section, so only the turns ahead of it stay cached; and the first pair of every session breaks benignly, simply because the session's first turn appears. Retention is the only kind the retention settings control.
-   **Mid-section removal is the most common break, and three mechanisms cause it:** across 89 assemblies carrying the shipped layout, 14 payload pairs lost a turn from the middle, against 12 pairs whose `## Session Resources` changed and 2 that truncated the front. Counting turns rather than pairs, those removals total 31: 12 came from a report that says `Validation Failed`, 10 from the token budget, 7 from a non-green plan, and 2 from retention. Validation pruning drops a turn whose plan the parser rejected, so it carries no executed work. The budget drops the largest selected turn-scope files until their total fits `auto_pruning.turn_context_threshold`, which makes how much history survives depend on how large a file a turn happened to read rather than on how much history is worth keeping. Plan-status pruning drops a turn whose status line is not `ON-TRACK 🟢`, and `OFF-TRACK 🟡` means the turn missed its expectation while gathering usable insight, so this mechanism deletes productive reasoning: the session that lost turns 4, 6 and 8 lost all three to `Validation Failed` reports, not here.
-   **A deeper retained history is not a caching win:** grading `max_turns_retention` against `retention_batch` on the 30-pair session scores the shipped 10/5 at 64.2% against 65.5% measured, a per-turn cadence at the same ceiling at 49.4%, and every higher-scoring cell retains strictly less history, either by pruning down to a single turn when the batch equals the ceiling or by never firing the prune inside the sampled window. Batching is worth roughly 15 percentage points against per-turn pruning; depth beyond that trades context for cache rather than gaining either.
-   **Shrinking a volatile section inflates this figure without caching anything:** the share is a ratio against total payload size, so trimming `## Resource Contents`, the project tree, or the runtime tail raises the percentage while leaving every cached byte where it was. Such a reduction is a context-cost decision, never a cache improvement.
-   **Post-history order is cosmetic:** permuting `## Git Status`, `## Project Structure`, and `## Resource Contents` in any way yields byte-identical served shares, because all three sit behind the point where the prefix has already ended. Their order is a readability decision, not a caching one.
-   **History must precede the volatile sections:** moving `## Session History` behind them scores 46.9% against 60.8% and loses on 25 of 39 pairs. Hoisting a section that changes between turns ahead of an append-only one can only tie (the section matched, so the prefix reached history anyway) or lose (it changed, so everything behind it is forfeited). It wins only on the turns where retention truncated the history, which is the minority case behind the 27.6% floor.
-   **History is the more cacheable growing section:** its own shared prefix averages 84 KB against 41 KB for `## Resource Contents`, and is larger in 25 of 33 comparable pairs.
-   **Ordering never changes what is pruned:** `_apply_global_budget` sorts its candidates by token count descending and retention counts distinct turn ids, so a resource's rendered position has no bearing on whether it survives.
-   **No ordering remedy for the largest section:** `## Resource Contents` contributes no cached bytes, but its size follows from the turn-scoped working set and the `read.max_lines` / `plan.max_lines` caps. Only giving the agent less content reduces it, which is a quality tradeoff rather than a format change.

---

### System Information

A simple key-value list of the environment details that stay constant for the whole session, giving the AI awareness of its operating environment without disturbing the byte-stable prefix.

-   **Rows, in order:** `CWD`, `OS`, `Shell`.
-   **Example:**
    ```markdown
    ## System Information
    - **CWD:** /Users/developer/projects/TeDDy
    - **OS:** Darwin 25.2.0
    - **Shell:** /bin/zsh
    ```

### Session Resources

In session mode, the files the session holds across turns render here, directly behind the header. These are the payload's most rewarding cacheable bytes: they usually change little between turns, so a provider serves them from cache instead of reprocessing them.

A file qualifies when it is listed in a scope other than `Turn` and is not part of this session's own history.

-   **Ordering:** Files render in the order the manifest reader returns them, which is alphabetical: both manifest write sites and the session repository collapse every path set with `sorted()`, so the roster is a sorted list rather than a chosen one. Declaration order in `.teddy/init.context` therefore never reaches the payload, and the manifest's order is not a knob today.
-   **Preserved turns stay in the history sequence:** a turn that answers with a `## Message`, or whose report carries `## User Request`, has its `plan.md` and `report.md` admitted to `session.context` instead of the turn-scoped working set. It still renders under `## Session History` at its chronological slot, never here, because a session's own history always renders there. What preservation buys is immunity from every turn-scoped heuristic, so each admitted pair anchors its position for the rest of the session: the earliest turns keep rendering at the head of the sequence, out of reach of retention front truncation, while the unpreserved turns around them fall away.
-   **Stability-ranked order loses:** ranking documents by how often they changed and rendering the most stable first scores 57.3% against 65.5% on a 30-pair session, and volatile-first ties at 65.1%, because a rank recomputed per payload flips the order between turns and a flip forfeits the prefix it was meant to protect. A fixed alphabetical order beats every forward-looking ranking measured so far.
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

Instead, they are appended in chronological order under a dedicated `## Session History` section using clean, human-readable turn headers (e.g. `### Initial Request`, `### Turn 1: Plan`, `### Turn 1: Report`) with all raw directory paths stripped out to keep the prompt concise and structured.

The section follows `## Session Resources`, so both stable parts of the session sit directly behind the header and form one growing cached prefix. Only the session's own root belongs here: a file read from another session is a resource, not our history.

-   **Communicating turns:** a turn that answered with a `## Message` instead of an action plan writes the same `plan.md` and `report.md`, so its content renders here as `### Turn N: Plan` / `### Turn N: Report`, never under `## Session Resources`.

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

    ### Turn 1: Report
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

Keeping them here holds per-turn values out of the byte-stable prefix, and the header above carries only the constant environment facts. The section renders in every mode, including a session-agnostic `teddy context` export, because those values exist regardless of session scope.

-   **Rows, in order:** `Current Date`, `Current Time`, `Current Turn`.
-   **Example:**
    ```markdown
    ## Runtime
    - **Current Date:** 2026-03-26
    - **Current Time:** 16:50:00
    - **Current Turn:** 02
    ```
