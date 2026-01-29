# Architectural Brief: Documentation Alignment

## 1. Goal (The "Why")

The strategic goal is to align the project's core documentation (`README.md` and `ARCHITECTURE.md`) with the significant architectural, workflow, and philosophical changes introduced in the preceding themes. With the implementation of the flattened structure, the Markdown parser, and the interactive session workflow, the documentation must be updated to serve as an accurate and useful guide for users and contributors.

This work is critical for maintaining project health and ensuring future development is consistent with the new standards.

## 2. Proposed Solution (The "What")

This is a documentation-centric initiative. The approach is to systematically refactor `README.md` and `ARCHITECTURE.md`, removing obsolete information and integrating the new concepts, commands, and components.

1.  **Refactor `README.md`:** The project's main entry point will be rewritten to reflect the new user-facing reality. This includes updating the project philosophy to "Obsidian for AI coding," describing the new session-based workflow (`teddy new`, `teddy resume`), and updating the command reference to match the new flattened CLI structure.

2.  **Refactor `ARCHITECTURE.md`:** The technical documentation will be overhauled to serve as an accurate reference for the new architecture. This involves updating all setup instructions (removing `poetry -C`), adding the new services (`SessionManager`, `ContextPayloadBuilder`, etc.) to the component map, and rewriting the Architectural Decision Records (ADRs) to document the new foundational principles like "File-Based Session Management" and "Markdown-First Plan & Report Format".

## 3. Implementation Analysis (The "How")

The review of `README.md` and `ARCHITECTURE.md` confirms that both documents require significant rewrites, not just minor edits. The core sections describing the tool's usage, installation, and architecture are fundamentally tied to the old `packages/executor` structure and YAML-based workflow.

-   **`README.md` Impact:** The entire section on "The `teddy` Executor" needs to be replaced. This includes the installation guide, the command reference, and the action reference. The project philosophy section should also be updated to explicitly state the "Markdown as UI" and "Local-First" principles.
-   **`ARCHITECTURE.md` Impact:** This document needs a structural overhaul. Obsolete setup instructions and conventions must be removed. The component map must be updated with the new services (`SessionManager`, `ContextPayloadBuilder`, etc.). The Architectural Decision Records (ADRs) need to be rewritten to reflect the new paradigms (File-Based Sessions, Markdown-First format, etc.), and the YAML plan specification must be replaced with a link to the canonical Markdown spec.

## 4. Vertical Slices

This brief will be implemented in two distinct vertical slices, one for each document.

---
### **Slice 1: Refactor `README.md`**
**Goal:** Update the main project `README.md` to reflect the new user-facing philosophy, workflow, and command structure.

-   **[ ] Task: Update Project Philosophy:** Replace the current introduction with the new "Obsidian for AI coding" philosophy and its guiding principles (Markdown as UI, Local-First, Transparency, Human-Centric).
-   **[ ] Task: Rewrite Executor & Workflow Section:** The entire section on the `teddy` executor needs a complete rewrite.
    -   Explain the new `.teddy/sessions` directory structure and its purpose.
    -   Describe the new primary workflow centered around the `teddy new` and `teddy resume` commands.
    -   Update the "Installation & Usage" guide to reflect the flattened project structure (i.e., no more `poetry -C packages/executor ...`).
-   **[ ] Task: Update Command Reference:** Replace the old command reference with the new, flat command structure: `new`, `plan`, `resume`, `branch`, `context`, and the session-unaware `execute`.
-   **[ ] Task: Update Action Reference:** Rename the "YAML Action Reference" to "Action Reference," state that plans are now authored in Markdown, and link to the canonical spec.
-   **[ ] Task: Update Roadmap:** Modify the project roadmap to mark the "Interactive Session Workflow" as complete.

---
### **Slice 2: Refactor `ARCHITECTURE.md`**
**Goal:** Update the architectural documentation to serve as an accurate technical reference for the new, flattened, session-based architecture.

-   **[ ] Task: Update Setup & Conventions:** Revise all setup instructions and commands to align with the flattened project structure. The `poetry -C` convention is obsolete and must be removed.
-   **[ ] Task: Update Component & Boundary Map:** Add the new services and ports introduced in the interactive workflow: `SessionManager`, `ContextPayloadBuilder`, `MarkdownReportFormatter`, `ConfigService`, and `ILlmClient`.
-   **[ ] Task: Rewrite Key Architectural Decisions (ADRs):**
    -   Remove obsolete ADRs related to the old plan format (e.g., "Separation of I/O Concerns," "Test Plan Injection").
    -   Add new ADRs for "File-Based Session Management," "Markdown-First Plan & Report Format," and "Dry-Run Pre-validation for Actions".
-   **[ ] Task: Replace Plan Specification:** Remove the entire "YAML Plan Specification" section and replace it with a "Markdown Plan Specification" section that links to the canonical spec in `docs/specs/new-plan-format.md`.
