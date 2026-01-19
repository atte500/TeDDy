# Brief: Interactive Session Workflow

This document defines the scope and technical approach for implementing a new interactive, file-based session workflow in `TeDDy`.

## 1. Problem Definition (The Why)

The current `TeDDy` workflow requires significant context-switching and manual copy-pasting between an external chat interface and the local terminal. This introduces friction and is incompatible with `TeDDy`'s design philosophy of using only the last turn's context for LLM calls.

The goal is to create a seamless, local-first, CLI-driven workflow that eliminates this friction. This new mode will provide users with complete ownership over session history, granular control over context, and an extensible framework for defining and chaining AI agent personas.

### Core Requirements:
-   **File-Based Session Management:** A CLI-driven system for starting, continuing, and branching conversations, where each turn is a separate Markdown file in a dedicated session folder.
-   **Conversation Traceability:** Each turn file will contain a unique `id` and a `parent_id` in its frontmatter, creating a traceable graph of the conversation that explicitly supports branching.
-   **Interactive Plan-Act Loop:** A persistent CLI loop that automates the generation and execution of plans, while retaining the existing step-by-step user approval for safety.
-   **Historical State Restoration:** A `teddy restore <turn_file.md>` command that can revert the project's entire file state to the snapshot associated with a specific turn.
-   **Tiered & Flexible Context Control:**
    -   A hierarchical system for managing context at the per-turn, per-session, and permanent levels.
    -   The `continue` command will support a `--context-depth <N>` flag to optionally include `N` previous turns in the LLM prompt, overriding the default "last message only" behavior.
-   **Extensible Agent Chaining:** An explicit, user-configurable system for chaining multiple LLM prompts to perform complex reasoning before generating a final plan.

## 2. Selected Solution (The What)

### State Management: Isolated Git Worktrees
The feature will be built around an **Isolated Worktree Strategy** for state management. This provides maximum safety by sandboxing all AI file operations, which aligns with `TeDDy`'s "Poka-Yoke" (Mistake-Proofing) principle. A successful plan execution results in a new Git commit, whose hash is stored in the turn file, enabling a robust `restore` capability.

### LLM Chaining: Explicit YAML Pipelines
To break down complex reasoning into smaller, more reliable steps, we will implement **Explicit Pipelines**. A user can define a multi-step LLM chain in a YAML file (e.g., `analysis -> decision -> plan`). The `SessionService` will execute this chain, passing the output of one step as the input to the next, before generating the final assistant response and plan.

### Quality of Life Features
-   **YAML Validation & Retry:** Before execution, the LLM-generated YAML plan will be validated against a schema. If validation fails, the system will automatically re-prompt the LLM with the validation error, asking it to correct the plan.
-   **Flexible User Input:**
    -   **CLI Flag:** The `start` and `continue` commands will accept an optional `-m "comment"` for one-off instructions.
    -   **Interactive Prompt:** When running interactively, the user will be prompted for an optional comment before the AI generates its next plan.
-   **Autonomous Execution Mode:** The `continue` command will feature a `--yolo` flag to run in a non-interactive, autonomous mode. In this mode, plans are executed automatically without step-by-step approval. The loop will only pause if the plan includes a `chat_with_user` action, waiting for user input before proceeding.

## 3. Implementation Analysis (The How)

### Repository Refactoring
The first step will be to simplify the project structure. The contents of `packages/executor/` will be moved to the project root, and the now-obsolete `packages/tui/` directory will be removed.

### Code-Level Plan
-   **`main.py`:** The main Typer app will be updated to reflect the new root structure and will host the new `teddy session` command group (`start`, `continue`, `restore`).
-   **`src/teddy/core/services/`:** A new `SessionService` will orchestrate the session workflow. A new `GitManager` service will encapsulate all `git worktree` logic. A `PipelineRunner` service will handle the execution of YAML-defined LLM chains.
-   **`src/teddy/core/domain/models/`:** New Pydantic models for `Session`, `Turn`, and `Pipeline` will be created.

## 4. Vertical Slices

This feature will be implemented in the following dependency-aware order:

-   [ ] **Slice 1: Project Restructuring.** Move all `packages/executor` content to the project root and delete `packages/tui`. Update all imports, `pyproject.toml`, and CI scripts.
    -   *Update `README.md` `Installation & Usage` section.*
-   [ ] **Slice 2: Session Scaffolding & Context.** Implement `teddy session start` and `continue` commands. Add `-m` and `--context-depth` flags, the interactive comment prompt, and the `id`/`parent_id` linking logic.
    -   *Update `README.md` `Command-Line Reference` for `start` and `continue`.*
-   [ ] **Slice 3: Core State Management & Autonomous Mode.** Implement the `git worktree` snapshot-and-commit logic in a `GitManager`. Integrate into the `continue` loop with the `--yolo` flag.
    -   *Update `README.md` `Session-Based Workflow` to explain state snapshots.*
-   [ ] **Slice 4: State Restoration.** Implement `teddy session restore <turn_file.md>`.
    -   *Update `README.md` `Command-Line Reference` for `restore`.*
-   [ ] **Slice 5: LLM Pipeline Execution.** Implement the `PipelineRunner` service to parse and execute pipeline YAML files.
    -   *Update `README.md` roadmap to reflect the new pipeline feature.*
-   [ ] **Slice 6: YAML Validation & Retry.** Integrate a validation and retry loop for LLM-generated plans.
    -   *Update `README.md` `Session-Based Workflow` to mention plan validation.*
