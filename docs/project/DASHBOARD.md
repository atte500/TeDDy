# TeDDy: A file-based AI coding workflow that puts you in control

The **TeDDy CLI** applies the **[UNIX philosophy](https://en.wikipedia.org/wiki/Unix_philosophy)** to AI development and uses a **[Git-like workflow](https://git-scm.com/)** to embed the entire collaboration process directly into your file system. Inspired by **[Obsidian](https://obsidian.md/)**, your entire AI collaboration lives exclusively in plain Markdown files in your local directory.

## 1. Guiding Principles

### 1.1. Markdown Files as Interface

With TeDDy, your interface *is* the file system. You interact with the AI through simple Markdown files that you can edit, search, and manage with the tools you already use every day. Your AI workflow lives and breathes alongside your code, not in a separate, siloed application.

### 1.2. Local-First & Data Ownership

Your complete AI collaboration history resides on your machine in a simple, open format. There is no cloud service, no vendor lock-in. This gives you absolute control over your privacy and full ownership of your data. Your sessions are as portable, private, and versionable as the rest of your codebase.

### 1.3. Stateless & Transparent

TeDDy is stateless by design. The AI's complete context is passed in as a file, and its results are written out as a file. This explicitness makes every turn completely transparent and auditable. Because the entire state is just text on your disk, the workflow is also incredibly hackable. Agent personas are defined in simple prompt files you can easily edit or create, allowing you to tailor the AI's skills, rules, and personality to perfectly fit your project's unique needs.

### 1.4. Human-Centric Workflow

Instead of executing actions directly, each turn, agents outline their plan using a **TeDDy-specific Markdown protocol** structured to clearly present the agent's rationale and every intended action for your approval, while also being precisely executable by the CLI. Once approved, the actions are executed *deterministically*, and the results are summarized in a Markdown execution report that is passed back to the AI to inform the next turn.

## Roadmap

This table tracks the status of high-level Milestones, their associated specifications, and the key features they deliver.

| Milestone                                                                                                  | Status        | Specs                                                                                                                                                               | Features                                                                     |
| ---------------------------------------------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [07-markdown-report-generator](./milestones/07-markdown-report-generator.md)                               | `In Progress` | [Manual CLI Workflow](./specs/manual-cli-workflow.md)<br>[Report Format](./specs/report-format.md)                                                                  | - Pre-flight plan validation<br>- Markdown-based execution reports           |
| [08-replace-markdownify-with-trafilatura](./milestones/08-replace-markdownify-with-trafilatura.md)         | `Planned`     | N/A                                                                                                                                                                 | - Replace `markdownify` with `trafilatura`<br>- Improve web scraping quality |
| [09-llm-client-and-config-service](./milestones/09-llm-client-and-config-service.md)                       | `Planned`     | [Foundational Restructuring](./specs/foundational-restructuring.md)                                                                                                 | - Centralized config service<br>- LLM client abstraction                     |
| [10-interactive-workflow-and-cli-refinements](./milestones/10-interactive-workflow-and-cli-refinements.md) | `Planned`     | [Interactive Session](./specs/interactive-session-workflow.md)<br>[Context Payload](./specs/context-payload-format.md)<br>[Report Format](./specs/report-format.md) | - File-based session management<br>- Interactive TUI for plan editing        |
| [11-documentation-alignment](./milestones/11-documentation-alignment.md)                                   | `Planned`     | N/A                                                                                                                                                                 | - Refactor `README.md`<br>- Refactor `ARCHITECTURE.md`                       |
| [12-refactor-legacy-dtos](./milestones/12-refactor-legacy-dtos.md)                                         | `Planned`     | N/A                                                                                                                                                                 | - Refactor legacy DTOs<br>- Modernize domain model structure                 |

## Workflow Standards

This section defines the conventions for our project management artifacts.

- **Artifact Lifecycle:** Work flows from `Spec` (the "why") -> `Milestone` (the "what") -> `Slice` (the "how").
- **Numbering:** Milestones and Slices are numbered sequentially.
- **Dashboard Policy:** The **Roadmap** table above tracks the status of high-level Milestones. The Pathfinder is the sole agent responsible for updating this table.
- **Archiving Policy:** Once a Milestone is completed, its entry is removed from the Roadmap table, and its corresponding `.md` file (along with its slices) is moved into an `archive/` subdirectory.
