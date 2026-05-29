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
- **Requirements:**
    - **CLI Polish:** Update `start` command to support `-a/--agent`, `-m/--message`, and `-c/--context` flags for fluid handoffs.
    - **Parser Cleanup:** Remove legacy `PROMPT`, `INVOKE`, and `RETURN` actions from `MarkdownPlanParser` and `PlanValidator`.
    - **Orchestrator:** Ensure `ExecutionOrchestrator` handles "Message Turns" (no actions) without side-effects.
    - **Prompt Migration:** Update all system prompts (`pathfinder`, `architect`, `developer`, `debugger`, `assistant`, `prototyper`) to use `## Message` for all communication and handoffs.

### TUI & CLI UX Polish
- **Core Goal:** Improve the interactive experience and provide better visibility into session state.
- **Requirements:**
    - **Navigation:** Alt+Up/Down for jumping between Context, Rationale, and Plan/Message sections.
    - **Context Interactions:** Pressing `e` on context nodes opens the corresponding file/context file in the external editor.
    - **Metadata Visibility:** Display model name and session cost (rounded to nearest cent) in the right panel when the Context Root is selected.
    - **Tier 2 Editing:** Automatically open external editor for parameters that are multiline or >100 characters.
    - **Truncation Hints:** If `EXECUTE` or `READ` output is truncated, provide specific instructions (e.g., "output to file and READ" or "use sed with line counts").
    - **Editor & Diff Mapping:** Strictly respect `editor` config; implement a translation table for diff flags (e.g., `nvim` -> `-d`); remove all implicit VS Code fallbacks.
    - **Layout:** Ensure consistent padding for Rationale items and Message sections to match the right and left panels.
    - **UX Hints:** Append reminder to user request messages: "Update reference documents accordingly if needed."
    - **Validation Logging:** Include concise versions of encountered errors in "Validation failed replanning" logs; remove the empty line before the message.
    - **RESEARCH Enhancement:** Scrape and return full contents/excerpts instead of just SERP snippets. Update instructions for all agents accordingly.
    - **CLI Polish:** Support `-a`, `-m`, and `-c` flags for the `start` command.

### Stability & Infrastructure
- **Core Goal:** Hardening the system against external failures and improving context management.
- **Requirements:**
    - **LLM Resilience:** Implement retry logic (3 attempts) for SSL and OpenRouter timeout errors (Reproduce via: `SSLV3_ALERT_BAD_RECORD_MAC`).
    - **Web Scraper (403 Bypassing):** Attempt to bypass 403 Forbidden errors via User-Agent rotation and common headers (Reproduce via: `https://www.pnas.org/doi/10.1073/pnas.2416294121`).
    - **GitHub Compatibility:** Fix content extraction for `raw.githubusercontent.com` links that currently return SUCCESS but empty content (Reproduce via: `https://raw.githubusercontent.com/lllyasviel/LayerDiffuse/main/README.md`).
    - **Safety Limits:** Implement `max-turns` (99) and `max-cost` ($5) limits in `config.yaml`, enforced strictly in `--yolo` (`-y`) mode.
    - **Context Robustness:** Recursive directory expansion for context paths; support remote URLs in `.context` files; strictly enforce deduplication.
    - **Session Migration:** Cap turns at 99 (2-digit padding); at turn 100, automatically migrate to a new continuation session (e.g., `name-2`) by cloning `session.context` and the active prompt and transition the `turn.context` exactly as a normal turn transition would to preserve the working context.
    - **Action Side-effects:** `CREATE` actions automatically add the new file path to the turn's context.
    - **Session Prompt Relocation:** Store `system_prompt.xml` at the session root rather than copying it into every turn directory.
    - **Session Efficiency:** In session mode, NEVER include resource contents in `report.md`; add config to prevent "Message Turns" from being pruned.
    - **EXECUTE Fail-Fast:** Detect interactive prompts to fail early; on timeout, identify the specific failing command in a chain.
    - **Mid-Execution Consistency:** Gracefully return `FAILURE` for `EDIT` actions if a file is modified during execution (e.g., by a preceding `EXECUTE`).
    - **Environment Hardening:** Suppress `LiteLLM`/`botocore` warnings in production environments.
    - **Parser Resilience:** For all actions (e.g., `READ`, `MESSAGE`), ignore and clean up unforeseen codeblocks, thematic breaks (`---`), or trailing text within codeblock delimiters (e.g., `~~~~~~ trailing text`) following the action block without triggering validation errors. (Note: Other unforeseen text outside delimiters must still raise validation error).
