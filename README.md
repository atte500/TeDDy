# TeDDy: Your Contract-First & Test-Driven Pair-Programmer

TeDDy is an AI-assisted coding paradigm that pairs you with a strategic **Architect AI** and a tactical **Developer AI** to build robust, verifiable software. It counters the instability of "agent-mode" AI development by enforcing engineering discipline through a workflow inspired by Contract-First Design principles and grounded in Test-Driven Development (TDD) practices.

## Conceptual Groundwork

For a detailed walkthrough of the concepts and principles behind TeDDy, please see the video overview:
[![Video Title](https://img.youtube.com/vi/VIDEO_ID/0.jpg)](https://www.youtube.com/watch?v=VIDEO_ID)

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

## The TeDDy Workflow: Architect & Developer

TeDDy structures the development process around two distinct AI personas, each with a specific **system prompt** and a clear mandate.

### 1. The Architect (Contract-First Design)

The Architect's role is to manage complexity by applying a holistic **Contract-First Design** philosophy. It establishes a cascade of agreements, starting with a user-approved **Public Contract** (`README.md`) that defines *what* the system does, and drills down into an **Architectural Contract** (`ARCHITECTURE.md`) and tactical **Implementation Contracts** that define *how* it's built.

> **`Prompts/architect.xml`**: A high-level planner that defines the public contract (`README.md`), the internal architecture (`ARCHITECTURE.md`), and the specific contracts for each layer of the application. **Its output is documentation.**

### 2. The Developer (Test-Driven Development)

The Developer's role is to implement the Architect's plan. It follows a strict, outside-in TDD workflow, ensuring that every line of code is written to satisfy a failing test, which in turn satisfies an architectural contract.

> **`Prompts/dev.xml`**: A hands-on implementer that executes the Architect's plan. It works in nested Red-Green-Refactor loops, starting with a failing end-to-end test and progressively implementing the system layer by layer. **Its output is code and tests.**

> **A Note on Parallel Development**
> Thanks to the clear contracts and separation of layers defined by the Architect, the Developer can generate plans for multiple layers in parallel within a single turn. This is controlled by the `<parallel_development>ENABLED</parallel_development>` setting in `Prompts/dev.xml`. While this accelerates progress, it can sometimes be challenging for the AI to manage. If you find the plans are becoming overly complex or losing context, you can switch this setting to `DISABLED` to force the Developer to work on one layer at a time.

## How to Use TeDDy

**Important First Step: Provide Project Context**

Before starting, it's crucial to give the AI a clear picture of your project's layout. This is mandatory for existing (brownfield) projects.

In your initial message to either the Architect or Developer, provide the complete file and directory tree of your project. This allows the AI to make informed decisions about where to read, create, or modify files.

You can generate this using the `tree` command or the recommended **Copy4AI** VS Code extension.

---

### Phase 1: Architecture

1.  Start a chat session in Google AI Studio.
2.  Add and save the content of `Prompts/architect.xml` as the "System instructions".
3.  **Provide the project file tree**, followed by a high-level business requirement.
4.  Iterate with the Architect until the public `README.md` and internal `ARCHITECTURE.md` are approved and all vertical slices and layer contracts are defined.

### Phase 2: Development

1.  Start a new chat session.
2.  Add and save the content of `Prompts/dev.xml` as the "System instructions".
3.  **Provide the project file tree** and the architectural documents generated by the Architect.
4.  Instruct the Developer to begin implementing the first vertical slice.

## Recommended Tooling

-   **Google AI Studio**: Add and save the provided system prompts under "System instructions" on the right-hand tab. Execute commands without any Tools enabled - Gemini 2.5 Pro is recommended.
-   **[Copy4AI](https://marketplace.visualstudio.com/items?itemName=LeonKohli.snapsource):** A VS Code extension to quickly copy file contents and the project structure to your clipboard. **This is the recommended way to perform the initial context-setting step mentioned above.**

## Understanding the AI's Plans

> **The Rationale Block: Tracing the AI's Logic**
> Every plan generated by both the Architect and the Developer is preceded by a `Rationale` block. It explicitly states the reasoning behind the current plan by analyzing the outcome of the previous step, stating a clear objective, and defining the criteria for success. This ensures every action is deliberate and provides a traceable history of the AI's decision-making process, which is critical for effective multi-turn collaboration.

The Architect and Developer AIs operate by generating structured **Plans**. Each plan has a clear **Goal** and a series of **Actions**. Your role is to act as the executor of these plans, applying the changes to your local workspace.

### Plan Types

Each persona has a specific set of plans they can generate:

#### Architect Plans
-   **`Information Gathering`**: Used to read files, ask you questions, or research external topics to fill knowledge gaps.
-   **`Spike`**: A time-boxed experiment to resolve a specific technical or functional unknown (e.g., testing a library) before committing to a design. The output is disposable.
-   **`EDIT Documentation`**: The primary plan type for creating and updating the canonical architecture documents in the `/docs/` directory.

#### Developer Plans
-   **`Information Gathering`**: Used to read architectural documents or ask for clarification.
-   **`RED Phase`**: To write a single new *failing* test (End-to-End, Layer, or Unit).
-   **`GREEN Phase`**: To write the *minimum* amount of implementation code required to make the current failing test pass.
-   **`REFACTOR Phase`**: To improve the internal structure of the code without changing its external behavior, done only when all tests are passing.
-   **`Version Control`**: To execute `git` commands for staging and committing code after a successful refactor cycle.

### Action Reference

These are the specific actions the AI can include in a plan:

-   **`CREATE FILE`**: Creates a new file with the specified content.
-   **`EDIT FILE`**: Modifies an existing file using a `FIND`/`REPLACE` block.
-   **`APPEND TO FILE`**: Adds content to the end of an existing file.
-   **`DELETE FILE`**: Removes a file, typically for cleaning up spike artifacts.
-   **`READ FILE`**: Reads the content of a file to gain context.
-   **`EXECUTE`**: Runs a shell command (e.g., to run tests or version control).
-   **`RESEARCH`**: Asks a set of specific questions. You can copy the research request and provide it to another AI (like Gemini, Perplexity, etc.) to get the answers.
-   **`CHAT WITH USER`**: The AI requires your feedback, approval, or specific information.

## Roadmap & Current Limitations

-   **Google AI Studio:** The current prompts are tailored for Google AI Studio and may require adjustments for other models and interfaces. The long-term goal is to make the prompts more model-agnostic.
-   **Manual Execution:** Plans generated by the AIs must be executed manually. The "Recommended Tooling" section above helps ease this process.
-   **UI Integration:** Integrating the TeDDy workflow directly into an open-source platform like **[LibreChat](https://www.librechat.ai/)** will allow for a more seamless, integrated user experience. 
-   **Prompt Size & Context Window:** The current system prompts are substantial (approx. 6,000 tokens for each). In long-running chat sessions, this can lead to faster "context rot", where the model's performance may degrade as the conversation history grows. The planned integration with **[LibreChat](https://www.librechat.ai/)** will address the prompt size limitation by leveraging the [agent chain feature](https://www.librechat.ai/docs/features/agents#agent-chain), which can decompose the large prompts into smaller, independent instructions and leverage the [benefits of a Mixture-of-Agents architecture](https://arxiv.org/abs/2406.04692).