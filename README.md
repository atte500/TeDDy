# TeDDy: Your Contract-First & Test-Driven Pair-Programmer

TeDDy is an AI-assisted coding paradigm that pairs you with a strategic **Architect AI** and a tactical **Developer AI**, supported by a specialist **Debugger AI**, to build robust, verifiable software. It counters the instability of "agent-mode" AI development by enforcing engineering discipline through a workflow inspired by Contract-First Design principles and grounded in Test-Driven Development (TDD) practices.

## Conceptual Groundwork for the Framework:

[![My Plan to Fix AI Coding](https://img.youtube.com/vi/By6wGuT-4sA/0.jpg)](https://www.youtube.com/watch?v=By6wGuT-4sA)

## DEMO:

[![DEMO: TeDDy AI Pair-Programmer - Building a Roguelike in Rust & Bevy](https://img.youtube.com/vi/4nM6e_2i54o/0.jpg)](https://www.youtube.com/watch?v=4nM6e_2i54o)

## The Problem: The AI Coding "Slot Machine"

Modern AI coding assistants are powerful but unpredictable. The experience often feels like playing a slot machine:
- **Initial Wins:** The first few code generations are impressive, leading to a feeling of rapid progress.
- **Rapid Decay:** This initial velocity quickly grinds to a halt as the complexity grows. You lose control of the code, and the cost of change skyrockets.
- **Compounding Errors:** LLMs tend to "guess" the final code without incremental verification. This leads to compounding errors that are difficult to untangle.

The [2025 DORA report on AI-assisted software development](https://services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf) confirms this observation: **software delivery instability leads to higher change failure rates and more rework.**

## The Solution: Quality by Design

The core issue is that software development is an iterative, sequential process. Unlike highly parallelizable problems where scale is the primary solution, software's main bottleneck is the **sequential, cognitive work of engineering**: asking the right questions, defining clear boundaries, and validating assumptions.

We take inspiration from the **Toyota Production System (TPS)**, which revolutionized manufacturing by shifting from end-of-line quality control to a "built-in quality" mindset.

Two key principles of TPS apply directly to software:

1.  **Jidoka (Autonomation):** *Stop the line immediately when a defect is found.* In software, a "defect" is a wrong assumption. Test-Driven Development (TDD) is our implementation of Jidoka, preventing flawed code from ever being integrated.
2.  **Poka-Yoke (Mistake-Proofing):** *Design processes so errors can't be made in the first place.* **Contract-First Design** is our Poka-Yoke. By defining clear "seams" and contracts between all parts of the system—starting with the user—we mistake-proof the architecture.

The objective is to improve **long-term** efficiency based on DORA's insight that **speed is a byproduct of quality.**

## The TeDDy Workflow: Pathfinder, Architect, Developer & Debugger

TeDDy structures the development process around four distinct AI personas, each with a specific **system prompt** and a clear mandate.

### 1. The Pathfinder (Strategic Discovery)

The Pathfinder is the entry point for any new feature or idea. Its role is to act as a **Strategic Pathfinder**, navigating the journey from a vague user goal to a concrete, validated, and technically-grounded plan. It uses a structured, iterative "Diverge-Converge" workflow to methodically explore the **Problem Space (Why)**, the **Solution Space (What)**, and finally the **Implementation Space (How)**.

The Pathfinder's final output is a canonical **Brief**, a document that defines the scope of work and breaks it down into a checklist of high-level vertical slices, ready for the Architect.

> **`Prompts/pathfinder.xml`**: A strategic partner that guides the user through a discovery process to produce a well-defined feature brief. **Its output is a brief and a backlog of vertical slices.**

### 2. The Architect (Contract-First Design)

The Architect's role is to take the **Brief** from the Pathfinder and manage its complexity by applying a holistic **Contract-First Design** philosophy. It establishes a cascade of agreements, starting with a user-approved **Public Contract** (`README.md`) that defines *what* the system does, and drills down into an **Architectural Contract** (`ARCHITECTURE.md`) and tactical **Implementation Contracts** that define *how* it's built.

> **`Prompts/architect.xml`**: A high-level planner that defines the public contract (`README.md`), the internal architecture (`ARCHITECTURE.md`), and the specific contracts for each layer of the application. **Its output is documentation.**

### 3. The Developer (Test-Driven Development)

The Developer's role is to implement the Architect's plan. It follows a strict, outside-in TDD workflow, ensuring that every line of code is written to satisfy a failing test, which in turn satisfies an architectural contract.

> **`Prompts/dev.xml`**: A hands-on implementer that executes the Architect's plan. It works in nested Red-Green-Refactor loops, starting with a failing end-to-end test and progressively implementing the system layer by layer. **Its output is code and tests.**

### 4. The Debugger (Fault Isolation)

The Debugger is a specialist agent activated only when another agent gets stuck (i.e., fails to achieve its `Expected Outcome` twice in a row). Its role is to be a **Systematic Fault Isolation Specialist**. It follows a rigorous, scientific method to find the verifiable root cause of a problem, operating under the principle of "First, Do No Harm"—it never modifies source code directly.

It works in three phases:
1.  **Hypothesis Generation:** Analyzes the failure and creates a checklist of potential root causes.
2.  **Systematic Verification:** Designs and runs minimal, isolated experiments (`spikes`) to test each hypothesis.
3.  **Synthesis & Solution:** Produces a formal Root Cause Analysis (RCA) report and a verified solution script, then hands off the solution and deactivates.

> **`Prompts/debugger.xml`**: A systematic debugger that uses the scientific method to find the root cause of failures. **Its output is a root-cause analysis report and a verified solution script.**

## The `teddy` Executor: The Hands of the AI

The `teddy` command-line tool, located in the `packages/executor` directory, is the bridge between AI-generated plans and your local filesystem. It allows for the safe, transparent, and user-supervised execution of development tasks.

### Execution Flow

1.  **Plan Generation:** An AI agent generates a multi-step plan in YAML format.
2.  **Execution:** You save the plan to a file (e.g., `plan.yaml`) and run `teddy` against it. The recommended way is to use the `--plan-file` option to avoid conflicts with interactive prompts.
3.  **Interactive Approval:** By default, `teddy` runs in interactive mode. It prints each action and prompts for your approval (`y/n`). If you reject a step, you will be prompted for an optional reason. The action is not performed, and the final report will mark it as `SKIPPED`, including your reason, confirming that no changes were made.
4.  **Execution Report:** After execution, `teddy` prints a pure YAML **Execution Report** to the console. This report is the single source of truth about the outcome of the plan and is pasted back to the AI to provide a complete feedback loop.

### Installation & Usage

The `teddy` executor is a command-line tool managed with Poetry.

#### 1. Installation
First, install the package and its dependencies. This command only needs to be run once.
```bash
# From the TeDDy project root, this installs the executor package.
poetry -C packages/executor install
```
This makes the `teddy` command available within the project's managed environment.

#### 2. Activating the Environment
To use the `teddy` command from any directory, you must first activate its virtual environment.

```bash
# From the project root on macOS / Linux:
source $(poetry -C packages/executor env info --path)/bin/activate
```
After running this, your shell prompt will change, indicating that you are now inside the `teddy-executor` environment. You can then navigate to any other project directory and use the `teddy` command directly.

### Command-Line Reference

#### Executing a Plan

Once your environment is active (see "Installation & Usage"), you can run the `teddy` command from any directory. It will execute its plan relative to your current working directory.

**Example:**
```bash
# Navigate to the project you want to work on
cd /path/to/my-web-app

# Execute a plan file located in this directory
teddy plan.yaml

# To automatically approve all steps, use the -y flag:
teddy plan.yaml -y
```

To streamline the workflow, commands that produce significant output (like `context` and `execute`) will now **copy their output to the clipboard by default**. A confirmation message will be printed to `stderr`. This behavior can be disabled by adding the `--no-copy` flag to the command.

#### Utility Commands

| Command      | Description                                                                                                                                                                                                                                                                                                                                      |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `context`    | Gathers and displays the project context, copying it to the clipboard by default. The command respects rules in both `.gitignore` and an optional `.teddyignore` file. Rules in `.teddyignore` take precedence, allowing you to re-include specific files for the AI's context that are ignored by `.gitignore` (e.g., using `!dist/bundle.js`). |
| `get-prompt` | Outputs the content of a system prompt (e.g., `dev`, `architect`). It searches for project-specific overrides in `.teddy/prompts/` before falling back to the packaged defaults.                                                                                                                                                                 |

#### Environment Variables

The `teddy` executor can be configured using the following environment variables:

| Variable          | Description                                                                                                                                                                                                                                                   |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TEDDY_DIFF_TOOL` | Specifies a custom command-line tool for viewing diffs during interactive plan approval. If set, this tool takes precedence over the default fallback (VS Code). The command string is parsed to support arguments, e.g., `export TEDDY_DIFF_TOOL="nvim -d"`. |

### YAML Action Reference

This section defines the contract for the YAML plans the AI can generate. For the full specification, see the executor's architectural documentation.

-   `create_file`
-   `read`
-   `edit`
-   `execute`
-   `chat_with_user`
-   `research`

---

## How to Use TeDDy

**Important First Step: Provide Project Context**

Before starting, it's crucial to give the AI a clear picture of your project's layout. This is mandatory for existing (brownfield) projects. In your initial message to any agent, provide the complete file and directory tree of your project.

### Phase 1: Pathfinder (Discovery)
1.  Start a chat session in Google AI Studio.
2.  Add and save the content of `Prompts/pathfinder.xml` as the "System instructions".
3.  **Provide a high-level goal or problem statement.**
4.  Collaborate with the Pathfinder as it guides you from the "Why" (problem) to the "What" (solution) and "How" (implementation). The final output is an approved **Brief**.

### Phase 2: Architecture (Planning)
1.  Start a new chat session.
2.  Add and save the content of `Prompts/architect.xml` as the "System instructions".
3.  **Provide the project file tree** and the **Brief** from the Pathfinder.
4.  Iterate with the Architect to produce the public `README.md` and internal `ARCHITECTURE.md`.

### Phase 3: Development (Implementation)
1.  Start a new chat session.
2.  Add and save the content of `Prompts/dev.xml` as the "System instructions".
3.  **Provide the project file tree** and the architectural documents from the Architect.
4.  Instruct the Developer to begin implementing the first vertical slice. The Developer will provide you with `plan.yaml` files to execute using the `teddy` tool.

### Phase 4: Debugging (When Needed)
This phase is only initiated when another agent enters a failure loop. Follow the instructions in the `Prompts/debugger.xml` system prompt.

## Recommended Tooling

-   **Google AI Studio**: Add and save the provided system prompts under "System instructions" on the right-hand tab. **Use Gemini 2.5 for this workflow.** Based on experience, **avoid using the latest Gemini 3 model**, as it can be less consistent in adhering to the strict, step-by-step instructions required by the TeDDy agents.
-   **[Copy4AI](https://marketplace.visualstudio.com/items?itemName=LeonKohli.snapsource):** A VS Code extension to quickly copy file contents and the project structure to your clipboard.
-   **SERP Scraper Bookmarklets**: To streamline the `RESEARCH` action, this repository includes bookmarklets that scrape search engine results (SERPs) and copy them to your clipboard as a clean Markdown list.

## 🗺️ Project Roadmap

Here's a look at our development priorities.

### Core Framework

|    Status     | Stage / Feature Set        | Description                                                                                                                                 |
| :-----------: | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
|  ✅ Completed  | **Agent Prompts v1**       | Core prompts for Architect, Developer, and Debugger are defined and functional.                                                             |
| ▶️ In Progress | **YAML Plan Generation**   | Refining agent prompts to reliably generate YAML-compliant plans, improving executor compatibility and reducing the need for manual fixes.  |
|   📝 Planned   | **Agents & Core Workflow** | Solidifying the interaction protocols and distribuition of responsibilities between agents to ensure a robust, repeatable workflow.         |
|   📝 Planned   | **Prompt Decomposition**   | Decompose large prompts into smaller, chained states. This improves reliability and enables using smaller, local models for specific tasks. |

### `teddy` Executor CLI

|    Status     | Stage / Feature Set               | Description                                                                                                                                                            |
| :-----------: | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  ✅ Completed  | **Core Action & Utility Support** | The foundational actions (`create`, `read`, `edit`, `execute`, `chat`, `research`) and the `context` utility command are fully implemented and stable.                 |
| ▶️ In Progress | **Interactive Session Workflow**  | A local-first, file-based workflow that eliminates chat UIs. Manages conversation history, context, and state snapshots directly on the filesystem with Git.           |
|   📝 Planned   | **Explicit YAML Pipelines**       | A robust, user-configurable system for chaining multiple LLM prompts to perform complex reasoning (e.g., analysis -> decision -> plan) before generating a final plan. |
|   📝 Planned   | **Autonomous Execution Mode**     | An enhancement to the session workflow that allows for continuous, unattended execution of AI-generated plans, pausing only for explicit user interaction points.      |
