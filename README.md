# TeDDy: Your Contract-First & Test-Driven Pair-Programmer

TeDDy is an AI-assisted coding paradigm that pairs you with a strategic **Architect AI** and a tactical **Developer AI** to build robust, verifiable software. It counters the instability of "agent-mode" AI development by enforcing engineering discipline through a workflow inspired by Contract-First Design principles and grounded in Test-Driven Development (TDD) practices.

## Conceptual Groundwork for the Framework:

[![Video Title](https://img.youtube.com/vi/By6wGuT-4sA/0.jpg)](https://www.youtube.com/watch?v=By6wGuT-4sA)

## DEMO:

[![Video Title](https://img.youtube.com/vi/4nM6e_2i54o/0.jpg)](https://www.youtube.com/watch?v=4nM6e_2i54o)

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

-   **Google AI Studio**: Add and save the provided system prompts under "System instructions" on the right-hand tab. Execute commands without any Tools enabled - Gemini 1.5 Pro is recommended.
-   **[Copy4AI](https://marketplace.visualstudio.com/items?itemName=LeonKohli.snapsource):** A VS Code extension to quickly copy file contents and the project structure to your clipboard. This is the recommended way to perform the initial context-setting step.
-   **SERP Scraper Bookmarklets**: To streamline the `RESEARCH` action, this repository includes bookmarklets that scrape search engine results (SERPs) and copy them to your clipboard as a clean Markdown list.
    -   **How to set them up:**
        1.  Open your browser's bookmarks manager.
        2.  Create a new bookmark.
        3.  For the "Name", enter something descriptive like `Scrape Google` or `Scrape DDG`.
        4.  For the "URL" or "Address", copy the entire content of one of the `.js` files from the `Bookmarklets/` directory, including the `javascript:` prefix.
        5.  Save the bookmark, preferably on your bookmarks bar for easy access.
    -   **How to use them:** When the AI requests research, run its queries on Google or DuckDuckGo, click your bookmark, and paste the resulting Markdown list of links directly back to the AI.

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
-   **`READ FILE`**: Reads the content of a local file to gain context. This can also be used to "read" a web page if you provide its content in Markdown format (many online tools or browser extensions can convert a web page to Markdown).
-   **`EXECUTE`**: Runs a shell command (e.g., to run tests or version control).
-   **`RESEARCH`**: Generates a list of search queries to investigate a topic. Your role is to: 1. Execute these queries on Google or DuckDuckGo. 2. Use the provided SERP Scraper bookmarklets to copy the search results as a Markdown list. 3. Paste this list back to the AI for analysis.
-   **`CHAT WITH USER`**: The AI requires your feedback, approval, or specific information.

## Roadmap & Current Limitations

-   **Google AI Studio:** The current prompts are tailored for Google AI Studio and may require adjustments for other models and interfaces. The long-term goal is to make the prompts more model-agnostic.
-   **Manual Execution:** Currently, plans generated by the AI must be applied to your local workspace manually. To streamline this, the AI will in the future also output a structured, machine-readable version of the plan (using e.g., YAML). This will enable automated execution via a local helper script.
-   **UI Integration:** Integrating the TeDDy workflow directly into an open-source platform like **[LibreChat](https://www.librechat.ai/)** will allow for a more seamless, integrated user experience.
-   **Prompt Size & Context Window:** The current system prompts are substantial, making them harder to maintain and for the AI to follow. The planned integration with **[LibreChat](https://www.librechat.ai/)** will allow to leverage the [agent chain feature](https://www.librechat.ai/docs/features/agents#agent-chain), in order to decompose the large prompts into smaller, independent instructions and benefit from a [Mixture-of-Agents architecture](https://arxiv.org/abs/2406.04692).