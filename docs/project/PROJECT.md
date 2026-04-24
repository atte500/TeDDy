# Project Dashboard

## 1. Guiding Principles: Quality by Design

1.  **Jidoka (Autonomation):** *Stop the line immediately when a defect is found.* We make errors obvious so they can be fixed, rather than masking them. Test-Driven Development (TDD) is our primary implementation of Jidoka, preventing flawed code from ever being integrated.
2.  **Poka-Yoke (Mistake-Proofing):** *Design processes so errors can't be made in the first place.* Contract-First Design is our Poka-Yoke. By defining clear "seams" and contracts between all parts of the system—starting with the user—we mistake-proof the architecture.
3.  **The UNIX Philosophy (Small, Sharp Tools):** *Build small, independent components that do one thing well and compose them to handle complexity.* This principle is the foundation of our architecture and development workflow. Each component is a "small, sharp tool" with a single responsibility, and they communicate through simple, well-defined contracts (Ports). This is embodied in our use of TDD to build focused functions, our Hexagonal Architecture to define clear boundaries, and our disciplined fault isolation process.

## Roadmap

This table tracks the status of active Milestones and provides a high-level summary of their included features.

| Milestone                                                                                | Status        | Specs                                                                                                                                                               | Features                                                                                        |
| :--------------------------------------------------------------------------------------- | :------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :---------------------------------------------------------------------------------------------- |
| [09-technical-debt-reconciliation](./milestones/09-architectural-debt-reconciliation.md) | `Completed`   | [DI Boundary Rules](./specs/di-boundary-rules.md)                                                                                                                   | Refactor ActionFactory to Constructor Injection, Enforce Core Isolation, Simplify Test Mocking. |
| [10-interactive-session-and-config](./milestones/10-interactive-session-and-config.md)   | `In Progress` | [Interactive Session](./specs/interactive-session-workflow.md)<br>[Context Payload](./specs/context-payload-format.md)<br>[Report Format](./specs/report-format.md) | Stateful Session Management, TUI Instruction Bridge, LLM Integration (LiteLLM), and UX Polish.  |

## Workflow Standards

This section defines the conventions for our project management artifacts.

- **Artifact Lifecycle:** Work flows from `Spec` -> `Milestone` -> `Slice`.
- **Numbering:** Milestones and Slices are numbered sequentially.
- **Dashboard Policy:** The **Roadmap** table above tracks the status of high-level Milestones.
- **Archiving Policy:** Once a Milestone is completed, its entry is removed from the Roadmap. The corresponding milestone and slice files are deleted. Git history serves as the official archive.
