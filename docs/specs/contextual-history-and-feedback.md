# Specification: Contextual History & Feedback Loop

## 1. Overview

This document specifies the design for a new set of features aimed at enhancing the AI's "memory" and improving the user-AI feedback loop. The core principle is to provide the AI with explicit, comprehensive context about its past actions, all while maintaining full transparency for the user.

## 2. Guiding Principles

- **Explicit is Better than Implicit:** All inputs to the AI (system prompt, user prompt) and all outputs (`plan.md`, `report.md`) will be stored as discrete, auditable files within the session turn.
- **Reproducibility:** Each turn directory must be a self-contained, reproducible artifact. Storing the full system prompt used for a turn is critical to this principle.
- **AI Agency over Context:** The AI has direct control over its working context via the `Active Context` block. The system must faithfully execute the AI's requested changes to this context.

## 3. New Turn Artifacts & Workflow

To support these principles, the directory structure and workflow for each turn will be updated.

- **New Structure:**
  ```
  01/
  ├── turn.context
  ├── _context.log
  ├── system_prompt.xml   # NEW: The exact system prompt used for this turn.
  ├── user_prompt.txt     # NEW: The user's prompt for this turn.
  ├── plan.md
  └── report.md
  ```
- **New `resume` Workflow:** When `teddy resume` detects a completed turn and must initiate a new planning phase, it **must** prompt the user for a new message. This message will be saved as `user_prompt.txt`.

## 4. Feature Specifications

### 4.1. Automatic Historical Context

- **Behavior:** When a new turn is initiated, the system automatically includes artifacts from the *previous* completed turn in the new context.
- **Implementation:**
  1. Locate the most recent turn that contains a `report.md`.
  2. The file paths for that turn's `plan.md`, `report.md`, and `user_prompt.txt` will be automatically added to the `Active Context` for the *new* turn.
- **Rationale:** This treats the AI's own history as part of its working context, allowing it to "read" its previous plan, report, and the user's prompt to inform its next action. By placing them in the `Active Context`, the AI can choose to prune them in a subsequent turn if they are no longer relevant.

### 4.2. Explicit Prompt Logging

- **Behavior:** The system will explicitly log the prompts used for generation.
- **`user_prompt.txt`**: The user's input message will be saved to this file at the start of a planning phase. This file serves the combined role of the initial prompt and any feedback on the previous turn.
- **`system_prompt.xml`**: The full text of the system prompt (e.g., from `prompts/pathfinder.xml`) used to generate the plan will be copied into this file.
- **Rationale:** This creates a fully auditable and reproducible record of every input that influenced the AI's plan.

### 4.3. Token-Aware & URL-Enabled Context Payload

- **Behavior:** The context payload (`_context.log`) sent to the AI will be enhanced.
- **Renaming:** The `## File Contents` section is renamed to `## Resource Contents`.
- **URL Support:** This section now supports URLs listed in the `.context` files. The system will scrape the URL and inject its content.
- **Token Counts:** Each resource will include a token count to help the AI make decisions about context pruning.
- **Format:**
  `````markdown
  ## 5. Resource Contents

  ---
  **Resource:** `[README.md](/README.md)`
  **Tokens:** 152
  ````markdown
  # TeDDy: Your Contract-First & Test-Driven Pair-Programmer
  ... (full file content) ...
  ````
  ---
  **Resource:** `https://example.com/api/docs`
  **Tokens:** 340
  ````markdown
  ...
  ````
  `````

### 4.4. Architectural Decision: `READ` Action Side-Effect

To balance auditability with token efficiency, the `READ` action will have a defined side-effect on the next turn's context.

- **System Behavior:**
  1. When the system successfully executes a `READ` action on a file resource, it checks if that file path is already part of the `Active Context` changes proposed by the AI in the current `plan.md`.
  2. If the file is **not** already being added, the system will **automatically add it to the context for the next turn**. This is a system-level rule.
- **Reporting Behavior:**
  - To prevent token duplication, the entry for the `READ` action in `report.md` will **not** contain the file's full content. It will contain a confirmation message that also explains the side-effect, for example: `Content was successfully read. The resource has been added to the context for the next turn.`
- **Rationale:** This was a user-directed architectural decision. It ensures that any information the AI reads is available for the next turn without requiring the AI to manage it explicitly, and it prevents the token duplication that would occur from having the same content in both the report and the next context payload.
