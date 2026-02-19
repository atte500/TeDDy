# TeDDy: A file-based AI coding workflow that puts you in control

The **TeDDy CLI** applies the **[UNIX philosophy](https://en.wikipedia.org/wiki/Unix_philosophy)** to AI development and uses a **[Git-like workflow](https://git-scm.com/)** to embed the entire collaboration process directly into your file system. Inspired by **[Obsidian](https://obsidian.md/)**, your entire AI collaboration lives exclusively in plain Markdown files in your local directory.

## 1. Guiding Principles

### 1.1. The File System is the UI
We interact exclusively through Markdown files. Our workflow is integrated with our code, allowing us to use standard editors and version control as our primary interface.

### 1.2. Local-First & Versionable
All session data and memory reside locally in plain text. This ensures absolute data ownership, privacy, and the ability to branch or revert our collaboration history just like our source code.

### 1.3. Explicit Context & Statelessness
Every turn is a standalone transaction. We pass the complete required context in and get a deterministic execution report out. This transparency ensures we always know *why* a decision was made.

### 1.4. Supervised Automation
Agents propose; humans dispose. We use a structured Markdown protocol to ensure every action is justified and approved before execution, maintaining a high-trust, "built-in quality" loop.

## Roadmap

This table tracks the status of high-level Milestones, their associated specifications, and the key features they deliver.

| Milestone                                                                                                  | Status        | Specs                                                                                                                                                               | Features                                                                     |
| ---------------------------------------------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [07-markdown-report-generator](./milestones/07-markdown-report-generator.md)                               | `In Progress` | [Manual CLI Workflow](./specs/manual-cli-workflow.md)<br>[Report Format](./specs/report-format.md)                                                                  | - Pre-flight plan validation<br>- Markdown-based execution reports           |
| [08-replace-markdownify-with-trafilatura](./milestones/08-replace-markdownify-with-trafilatura.md)         | `Planned`     | N/A                                                                                                                                                                 | - Replace `markdownify` with `trafilatura`<br>- Improve web scraping quality |
| [09-llm-client-and-config-service](./milestones/09-llm-client-and-config-service.md)                       | `Planned`     | [Foundational Restructuring](./specs/foundational-restructuring.md)                                                                                                 | - Centralized config service<br>- LLM client abstraction                     |
| [10-interactive-workflow-and-cli-refinements](./milestones/10-interactive-workflow-and-cli-refinements.md) | `Planned`     | [Interactive Session](./specs/interactive-session-workflow.md)<br>[Context Payload](./specs/context-payload-format.md)<br>[Report Format](./specs/report-format.md) | - File-based session management<br>- Interactive TUI for plan editing        |
| [11-refactor-legacy-dtos](./milestones/11-refactor-legacy-dtos.md)                                         | `Planned`     | N/A                                                                                                                                                                 | - Refactor legacy DTOs<br>- Modernize domain model structure                 |

## Workflow Standards

This section defines the conventions for our project management artifacts.

- **Artifact Lifecycle:** Work flows from `Spec` -> `Milestone` -> `Slice`.
- **Numbering:** Milestones and Slices are numbered sequentially.
- **Dashboard Policy:** The **Roadmap** table above tracks the status of high-level Milestones.
- **Archiving Policy:** Once a Milestone is completed, its entry is removed from the Roadmap table, and its corresponding `.md` file (along with its slices) is moved into an `archive/` subdirectory.
