# Architectural Brief: Documentation Alignment

## 1. Goal (The "Why")

The strategic goal is to align the project's core documentation (`README.md` and `ARCHITECTURE.md`) with the significant architectural and philosophical changes introduced in briefs `05` and `06`. With the implementation of the Markdown parser and the interactive session workflow, the project has fully adopted the "Obsidian for AI coding" philosophy, and the documentation must be updated to reflect this new reality.

This work is critical for maintaining project health, ensuring future development is consistent with the new standards, and providing a clear, accurate guide for users and contributors.

## 2. Architectural Approach (The "What")

This is a documentation-centric task. The approach is to systematically refactor `README.md` and `ARCHITECTURE.md` to remove obsolete information and integrate the concepts, commands, and components from the new session-based workflow.

The work will be divided into two main slices, one for each document, to ensure a focused and thorough update.

## 3. Implementation Slices (The "How")

This brief will be implemented in two distinct vertical slices.

---
### **Slice 1: Refactor `README.md`**
**Goal:** Update the main project `README.md` to reflect the new user-facing philosophy, workflow, and command structure.

-   **[ ] Task: Update Project Philosophy:** Replace the current introduction with the new "Obsidian for AI coding" philosophy and its guiding principles (Markdown as UI, Local-First, Transparency, Human-Centric).
-   **[ ] Task: Rewrite Executor & Workflow Section:** The entire section on the `teddy` executor needs a complete rewrite.
    -   Explain the new `.teddy/sessions` directory structure and its purpose.
    -   Describe the new primary workflow centered around the `teddy new` and `teddy resume` commands.
    -   Update the "Installation & Usage" guide to reflect the flattened project structure (i.e., no more `poetry -C packages/executor ...`).
-   **[ ] Task: Update Command Reference:** Replace the old command reference with the new, flat command structure: `new`, `plan`, `resume`, `branch`, and the session-unaware `execute`.
-   **[ ] Task: Update Action Reference:** Rename the "YAML Action Reference" to simply "Action Reference". State that plans are now authored in Markdown and link to `ARCHITECTURE.md` for the detailed specification.
-   **[ ] Task: Update Roadmap:** Modify the project roadmap to reflect that the "Interactive Session Workflow" is now complete.

---
### **Slice 2: Refactor `ARCHITECTURE.md`**
**Goal:** Update the architectural documentation to serve as an accurate technical reference for the new, flattened, session-based architecture.

-   **[ ] Task: Update Setup & Conventions:** Revise all setup instructions, commands, and file paths to align with the flattened project structure. The `poetry -C` convention is obsolete and must be removed.
-   **[ ] Task: Update Component & Boundary Map:** Add the new services and ports that were introduced to support the interactive workflow:
    -   `SessionManager` Service (`ISessionManager`, `LocalSessionManagerAdapter`)
    -   `ConfigService`
    -   `ILlmClient` Port & `LiteLLMAdapter`
    -   `MarkdownReportFormatter`
-   **[ ] Task: Rewrite Key Architectural Decisions (ADRs):** This section requires a major overhaul.
    -   **Remove Obsolete ADRs:** The decisions related to the old plan format and execution model are no longer relevant (e.g., "Separation of I/O Concerns," "Test Plan Injection," "Context Configuration").
    -   **Add New ADRs:** Document the new foundational principles: "File-Based Session Management," "Markdown-First Plan & Report Format," "Cascading Context (`global.context`, `session.context`)", and "Dry-Run Pre-validation for Actions".
-   **[ ] Task: Replace Plan Specification:** The entire "YAML Plan Specification" section must be removed and replaced with a new "Markdown Plan Specification" section. This section should provide a concise summary of the `plan.md` format and link to the canonical spec in `docs/specs/new-plan-format.md` for full details.
