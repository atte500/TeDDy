# Project: TeDDy

## Product Vision

TeDDy's mission is to apply the **UNIX philosophy** to AI development and create a **Git-like workflow** to embed the entire AI collaboration process directly into the file system.

- **Markdown Files as Interface:** The interface *is* the file system. AI collaboration lives exclusively in plain Markdown files in the local directory, managed with standard developer tools.
- **Local-First & Data Ownership:** No cloud lock-in. Total control over privacy and data. The complete workflow and context history resides on the local machine in a portable, open format.
- **Stateless & Transparent:** Context goes in as a file, results come out as a file. Every turn is completely deterministic, auditable, and hackable.
- **Human-Centric Workflow:** Action plans are reviewed and approved interactively before execution. A suite of specialized AI personas (Pathfinder, Architect, Developer, Debugger) tackle distinct phases of the software lifecycle using disciplined, proven workflows.

## Guiding Principles

1.  **Jidoka (Autonomation):** *Stop the line immediately when a defect is found.* We make errors obvious so they can be fixed, rather than masking them. Test-Driven Development (TDD) is our primary implementation of Jidoka, preventing flawed code from ever being integrated.
2.  **Poka-Yoke (Mistake-Proofing):** *Design processes so errors can't be made in the first place.* Contract-First Design is our Poka-Yoke. By defining clear "seams" and contracts between all parts of the system—starting with the user—we mistake-proof the architecture.
3.  **The UNIX Philosophy (Small, Sharp Tools):** *Build small, independent components that do one thing well and compose them to handle complexity.* This principle is the foundation of our architecture and development workflow. Each component is a "small, sharp tool" with a single responsibility, communicating through simple, well-defined contracts (Ports).

## Workflow Standards

This section defines the conventions for our project management artifacts.

- **Artifact Lifecycle:** Work flows from `Spec` -> `Milestone` -> `Slice`.
- **Numbering:** Artifacts are numbered sequentially using an `MM-NN-name.md` format, where `MM` represents the target Milestone number and `NN` represents the specific Slice or Case File number. For ad-hoc tasks not tied to an active milestone, `00` is used as the Milestone prefix (e.g., `00-01-ad-hoc-feature.md`).
- **Archiving Policy:** Once a feature slice or milestone is fully implemented and merged, its active planning artifacts can be deleted. The Git history serves as the official, permanent archive.

## Roadmap

### Structural Protocol & Parser
- **Core Goal:** Move from action-based communication (`INVOKE`, `RETURN`, `PROMPT`) to the structural `## Message` protocol.
- **Key Deliverables:**
    - `MarkdownPlanParser` update to support `## Message` section.
    - `ExecutionOrchestrator` update to handle "Message Turns" (no actions, just a report of the message).
    - Hard deprecation of legacy actions.
    - Update all system prompts in `src/teddy_executor/resources/prompts/` to follow the new protocol.

### TUI & CLI UX Polish
- **Core Goal:** Improve the interactive experience and provide better visibility into session state.
- **Key Deliverables:**
    - Alt+Up/Down navigation for jumping between Context, Rationale, and Plan/Message sections.
    - Context Node Editing: Pressing `e` on context nodes opens the corresponding file/context file in the external editor.
    - Metadata Visibility: Display model name and session cost (rounded to nearest cent) in the TUI when the Context Root is selected.
    - Parameter Editing: Automatically open external editor for multiline or long text parameters in the TUI review.
    - Smart Editor & Diff Mapping: Implement a translation table to automatically derive diff flags from the `editor` configuration (e.g., `nvim` -> `-d`), removing implicit fallbacks to VS Code.
    - CLI Abbreviations: Support `-a`, `-m`, and `-c` flags for the `start` command.

### Stability & Infrastructure
- **Core Goal:** Hardening the system against external failures and improving context management.
- **Key Deliverables:**
    - Resilience: Implement 403 error bypassing (User-Agent rotation/headers) and SSL retry logic.
    - Context Robustness: Recursive directory expansion for context paths and deduplication of resources.
    - Environment Hardening: Suppress `LiteLLM`/`botocore` warnings in production deployments.
    - Reliability: Handle cases where files are modified *during* execution (e.g., by an `EXECUTE` command) to prevent orchestrator crashes.
