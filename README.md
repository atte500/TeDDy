# TeDDy: A file-based AI coding workflow that puts you in control

The **TeDDy CLI** applies the **[UNIX philosophy](https://en.wikipedia.org/wiki/Unix_philosophy)** to AI development and uses a **[Git-like workflow](https://git-scm.com/)** to embed the entire collaboration process directly into your file system. Inspired by **[Obsidian](https://obsidian.md/)**, your entire AI collaboration lives exclusively in plain Markdown files in your local directory.

[![My Plan to Fix AI Coding](https://img.youtube.com/vi/By6wGuT-4sA/0.jpg)](https://www.youtube.com/watch?v=By6wGuT-4sA)

## Guiding Principles

### 1. Markdown Files as Interface

With TeDDy, your interface *is* the file system. You interact with the AI through simple Markdown files that you can edit, search, and manage with the tools you already use every day. Your AI workflow lives and breathes alongside your code, not in a separate, siloed application.

### 2. Local-First & Data Ownership

Your complete AI collaboration history resides on your machine in a simple, open format. There is no cloud service, no vendor lock-in. This gives you absolute control over your privacy and full ownership of your data. Your sessions are as portable, private, and versionable as the rest of your codebase.

### 3. Stateless & Transparent

TeDDy is stateless by design. The AI's complete context is passed in as a file, and its results are written out as a file. This explicitness makes every turn completely transparent and auditable. Because the entire state is just text on your disk, the workflow is also incredibly hackable. Agent personas are defined in simple prompt files you can easily edit or create, allowing you to tailor the AI's skills, rules, and personality to perfectly fit your project's unique needs.

### 4. Human-Centric Workflow

Instead of executing actions directly, each turn, agents outline their plan using a **TeDDy-specific Markdown protocol** structured to clearly present the agent's rationale and every intended action for your approval, while also being precisely executable by the CLI. Once approved, the actions are executed *deterministically*, and the results are summarized in a Markdown execution report that is passed back to the AI to inform the next turn.

## The TeDDy Workflow: Pathfinder, Architect, Developer & Debugger

TeDDy structures the development process around four distinct AI personas, each with a specific mandate.

### 1. The Pathfinder (Strategic Discovery)
The Pathfinder navigates the journey from a vague idea to a technically-grounded plan. It uses a structured **Diverge-Converge** workflow to explore the **Problem Space (Why)**, **Solution Space (What)**, and **Implementation Space (How)**.

### 2. The Architect (Contract-First Design)
The Architect manages complexity by applying a **Contract-First Design** philosophy. It establishes a cascade of agreements: from the **Public Contract** (`README.md`) to the **Architectural Contract** (`ARCHITECTURE.md`) and tactical port interfaces.

### 3. The Developer (Outside-In TDD)
The Developer implements the plan using a disciplined, **Outside-In TDD** workflow. It works in nested **Red-Green-Refactor** loops, ensuring every line of code is traceable to a business requirement.

### 4. The Debugger (Scientific Fault Isolation)
The Debugger is a specialist agent activated when others fail. It follows the **scientific method** to isolate the verifiable root cause of a problem.

## The `teddy` CLI: The Hands of the AI

The `teddy` command-line tool, is the bridge between AI-generated plans and your local filesystem. It allows for the safe, transparent, and user-supervised execution of development tasks, both in interactive as well as non-interactive mode.

### Execution Flow

1.  **Plan Generation:** An AI agent generates a multi-step plan in **Markdown format**.
2.  **Supervised Execution:** You run the `teddy execute` command against the plan.
3.  **Interactive Approval:** `teddy` prints each action and prompts for your approval (`y/n`). If you reject a step, it is marked as `SKIPPED`, and no changes are made.
4.  **Markdown Report:** After execution, `teddy` generates a Markdown **Execution Report** and copies it to your clipboard. This report is passed back to the AI to close the loop.

### Installation & Usage

The `teddy` executor is a CLI tool managed with **Poetry**.

#### 1. Installation
```bash
# From the project root, install the environment
poetry install
```

#### 2. Usage
To run commands, use `poetry run teddy <command>`.

### Command-Line Reference

| Command      | Description                                                                                                                            |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| `execute`    | Executes a Markdown plan file. If no file is provided, it reads the plan from the clipboard.                                           |
| `context`    | Gathers project context (file tree + selected file contents) and copies it to the clipboard. Respects `.gitignore` and `.teddyignore`. |
| `get-prompt` | Retrieves a system prompt (e.g., `pathfinder`, `dev`). Searches in `.teddy/prompts/` for overrides before falling back to defaults.    |

To streamline the workflow, `execute` and `context` **copy their output to the clipboard by default**. Use the `--no-copy` flag to disable this behavior.

## Project Roadmap

Here's a look at our development priorities.

|  Status   | Stage / Feature Set               | Description                                                                                                                                                  |
| :-------: | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Completed | **Agent Prompts v1**              | Core prompts for Pathfinder, Architect, Developer, and Debugger are defined and functional.                                                                  |
| Completed | **Core Action & Utility Support** | The foundational actions (`create`, `read`, `edit`, `execute`, `chat`, `research`) and the `context` utility command are fully implemented and stable.       |
|    WIP    | **Interactive Session Workflow**  | A local-first, file-based workflow that eliminates chat UIs. Manages conversation history, context, and state snapshots directly on the filesystem with Git. |
