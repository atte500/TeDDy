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

## The TeDDy Workflow: Architect, Developer & Debugger

TeDDy structures the development process around three distinct AI personas, each with a specific **system prompt** and a clear mandate.

### 1. The Architect (Contract-First Design)

The Architect's role is to manage complexity by applying a holistic **Contract-First Design** philosophy. It establishes a cascade of agreements, starting with a user-approved **Public Contract** (`README.md`) that defines *what* the system does, and drills down into an **Architectural Contract** (`ARCHITECTURE.md`) and tactical **Implementation Contracts** that define *how* it's built.

> **`Prompts/architect.xml`**: A high-level planner that defines the public contract (`README.md`), the internal architecture (`ARCHITECTURE.md`), and the specific contracts for each layer of the application. **Its output is documentation.**

### 2. The Developer (Test-Driven Development)

The Developer's role is to implement the Architect's plan. It follows a strict, outside-in TDD workflow, ensuring that every line of code is written to satisfy a failing test, which in turn satisfies an architectural contract.

> **`Prompts/dev.xml`**: A hands-on implementer that executes the Architect's plan. It works in nested Red-Green-Refactor loops, starting with a failing end-to-end test and progressively implementing the system layer by layer. **Its output is code and tests.**

### 3. The Debugger (Fault Isolation)

The Debugger is a specialist agent activated only when the Architect or Developer gets stuck (i.e., fails to achieve its `Expected Outcome` twice in a row). Its role is to be a **Systematic Fault Isolation Specialist**. It follows a rigorous, scientific method to find the verifiable root cause of a problem, operating under the principle of "First, Do No Harm"—it never modifies source code directly.

It works in three phases:
1.  **Hypothesis Generation:** Analyzes the failure and creates a checklist of potential root causes.
2.  **Systematic Verification:** Designs and runs minimal, isolated experiments (`spikes`) to test each hypothesis.
3.  **Synthesis & Solution:** Produces a formal Root Cause Analysis (RCA) report and a verified solution script, then hands off the solution and deactivates.

> **`Prompts/debugger.xml`**: A systematic debugger that uses the scientific method to find the root cause of failures. **Its output is a root-cause analysis report and a verified solution script.**

## The `teddy` Executor: The Hands of the AI

The `teddy` command-line tool, located in the `/executor` directory, is the bridge between AI-generated plans and your local filesystem. It allows for the safe, transparent, and user-supervised execution of development tasks.

### Execution Flow

1.  **Plan Generation:** An AI agent generates a multi-step plan in YAML format.
2.  **Execution:** You save the plan to a file (e.g., `plan.yaml`) and run `teddy` against it. The recommended way is to use the `--plan-file` option to avoid conflicts with interactive prompts.
3.  **Interactive Approval:** By default, `teddy` runs in interactive mode. It prints each action and prompts for your approval (`y/n`). If you reject a step, you will be prompted for an optional reason. The action is not performed, and the final report will mark it as `SKIPPED`, including your reason, confirming that no changes were made.
4.  **Execution Report:** After execution, `teddy` prints a pure YAML **Execution Report** to the console. This report is the single source of truth about the outcome of the plan and is pasted back to the AI to provide a complete feedback loop.

### Installation & Dependencies

The `teddy` tool is managed using `Poetry` and requires Python 3.9+. To work with the executor, first navigate to its directory:
```bash
cd executor
```

Then, use Poetry to install the dependencies and the tool in editable mode:
```bash
# This will create a virtual environment and install all dependencies
poetry install
```

### Command-Line Reference

All `teddy` commands must be run from within the `executor/` directory.

#### Executing a Plan

To avoid conflicts between plan input and interactive prompts (like `y/n` approval or `chat_with_user`), plans must be passed using the `--plan-file` option. Standard input (`stdin`) is now reserved exclusively for interactive I/O.

**From a File:**
```bash
# 1. Save the AI-generated plan to a file (e.g., plan.yaml)
# 2. Execute the plan with interactive approval:
poetry run teddy --plan-file plan.yaml

# To automatically approve all steps, use the -y flag:
poetry run teddy --plan-file plan.yaml -y
```

#### Utility Commands

| Command   | Description                                                                                                                          |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `context` | Gathers and displays the project context, including environment info and the contents of files specified in `.teddy/` configuration. |

### YAML Action Reference

This section defines the contract for the YAML plans the AI can generate. For the full specification, see the executor's architectural documentation.

-   `create_file`
-   `read`
-   `edit`
-   `execute`
-   `chat_with_user`
-   `research`

## How to Use TeDDy

**Important First Step: Provide Project Context**

Before starting, it's crucial to give the AI a clear picture of your project's layout. This is mandatory for existing (brownfield) projects. In your initial message to any agent, provide the complete file and directory tree of your project.

### Phase 1: Architecture
1.  Start a chat session in Google AI Studio.
2.  Add and save the content of `Prompts/architect.xml` as the "System instructions".
3.  **Provide the project file tree**, followed by a high-level business requirement.
4.  Iterate with the Architect until the public `README.md` and internal `ARCHITECTURE.md` are approved.

### Phase 2: Development
1.  Start a new chat session.
2.  Add and save the content of `Prompts/dev.xml` as the "System instructions".
3.  **Provide the project file tree** and the architectural documents.
4.  Instruct the Developer to begin implementing the first vertical slice. The Developer will provide you with `plan.yaml` files to execute using the `teddy` tool.

### Phase 3: Debugging (When Needed)
This phase is only initiated when the Developer or Architect AI enters a failure loop. Follow the instructions in the `Prompts/debugger.xml` system prompt.

## Recommended Tooling

-   **Google AI Studio**: Add and save the provided system prompts under "System instructions" on the right-hand tab. **Use Gemini 2.5 for this workflow.** Based on experience, **avoid using the latest Gemini 3 model**, as it can be less consistent in adhering to the strict, step-by-step instructions required by the TeDDy agents.
-   **[Copy4AI](https://marketplace.visualstudio.com/items?itemName=LeonKohli.snapsource):** A VS Code extension to quickly copy file contents and the project structure to your clipboard.
-   **SERP Scraper Bookmarklets**: To streamline the `RESEARCH` action, this repository includes bookmarklets that scrape search engine results (SERPs) and copy them to your clipboard as a clean Markdown list.

## 🗺️ Project Roadmap

Here's a look at our development priorities. We use the following statuses to indicate progress:

- 📝 **Planned:** The feature is on our agenda and is being scoped for a future release.
- ▶️ **In Progress:** The feature is in active development.
- ✅ **Completed:** The feature has been released.

### Core Framework

| Status | Stage / Feature Set      | Description                                                                                                                     |
| :----: | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
|   ✅    | **Agent Prompts v1**     | Core prompts for Architect, Developer, and Debugger are defined and functional.                                                 |
|   ✅    | **Conceptual Workflow**  | The high-level workflow for using the TeDDy paradigm is documented.                                                             |
|   📝    | **Prompt Agnosticism**   | Refine prompts to be more model-agnostic and less tied to a specific platform like Google AI Studio.                            |
|   📝    | **Prompt Decomposition** | Decompose large prompts into smaller, chained instructions to improve reliability and leverage Mixture-of-Agents architectures. |

### `teddy` Executor CLI

| Status | Stage / Feature Set               | Description                                                                                                                                                      |
| :----: | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|   ✅    | **Core Action & Utility Support** | The foundational actions (`create`, `read`, `edit`, `execute`, `chat`, `research`) and the `context` utility command are fully implemented and stable.           |
|   📝    | **TUI for LLM Interaction**       | Create a Terminal User Interface (TUI) to directly call LLM APIs, pass context, manage prompts, and execute the resulting plans in a seamless, interactive loop. |