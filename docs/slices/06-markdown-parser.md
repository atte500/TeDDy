# Vertical Slice: Markdown Plan Parser

- **Source Brief:** [Architectural Brief: Markdown Plan Parser](./../briefs/06-markdown-parser.md)
- **Specification:** [New Plan Format Specification](./../specs/new-plan-format.md)

## 1. Business Goal

To enhance the user experience and transparency of the `teddy` executor by transitioning the AI-generated plan format from YAML to a more readable and author-friendly Markdown structure, while ensuring full backwards compatibility with the existing YAML format.

## 2. Acceptance Criteria (Scenarios)

### Scenario: Successfully execute a Markdown plan
- **Given:** A valid `plan.md` file exists, conforming to the new plan format specification.
- **When:** The user executes the command `teddy plan.md`.
- **Then:** The `teddy` executor should successfully parse and execute all actions in the plan, producing a successful execution report.

**Example:**
- **Given:** The file `plan.md` contains:
  `````markdown
  # Create a test file
  - **Status:** Green 🟢
  - **Plan Type:** Implementation
  - **Agent:** Developer
  - **Goal:** Create a simple file.

  ## Action Plan

  ### `CREATE`
  - **File Path:** [hello.txt](/hello.txt)
  - **Description:** Create a hello world file.
  ````text
  Hello, world!
  ````
  `````
- **When:** The user runs `teddy plan.md -y`.
- **Then:** A file named `hello.txt` is created with the content "Hello, world!".

### Scenario: Backwards compatibility with YAML plans
- **Given:** A valid `plan.yaml` file exists.
- **When:** The user executes the command `teddy plan.yaml`.
- **Then:** The `teddy` executor should successfully parse and execute the YAML plan as it did previously.

### Scenario: Correctly parse all action types from Markdown
- **Given:** A `plan.md` file containing one of each action type (`CREATE`, `READ`, `EDIT`, `EXECUTE`, `RESEARCH`, `CHAT_WITH_USER`, `INVOKE`, `PRUNE`).
- **When:** The plan is parsed by the `MarkdownPlanParser`.
- **Then:** The resulting `Plan` domain object contains a correctly structured `Action` object for each action type, with all parameters accurately extracted from the Markdown AST.

### Scenario: Fence pre-processor corrects invalid nesting
- **Given:** A raw string from an LLM containing improperly nested Markdown code fences.
- **When:** The string is passed through the `FencePreProcessor`.
- **Then:** The output string is valid Markdown with corrected fence markers, ready for parsing.

## 3. Architectural Changes

This slice requires the following architectural modifications. The Architect will create or update the design document for each component before implementation begins.

-   **New Port:** An abstract `IPlanParser` port will be created to define the contract for all plan parsers.
-   **Refactor Service:** The existing `PlanParser` service will be renamed to `YamlPlanParser` and will implement the new `IPlanParser` port.
-   **New Service:** A new `MarkdownPlanParser` service will be created. It will implement `IPlanParser` and use the `mistletoe` library to parse Markdown plans. This service will include a fence pre-processing utility.
-   **Adapter Update:** The `CLI Adapter` (`main.py`) will be updated to include a factory mechanism that inspects the plan file type (`.md` or `.yaml`) and injects the appropriate parser implementation at runtime.

## 4. Interaction Sequence

1.  The `CLI Adapter` receives the path to a plan file (e.g., `plan.md`).
2.  It uses a new `PlanParserFactory` to determine the plan's type based on the file extension.
3.  The factory instantiates the correct parser implementation (e.g., `MarkdownPlanParser`).
4.  The `MarkdownPlanParser` first passes the file content through a `FencePreProcessor` utility to ensure the Markdown is valid.
5.  The service then uses the `mistletoe` library to parse the corrected content into an Abstract Syntax Tree (AST).
6.  The service traverses the AST, extracting the plan metadata and actions to construct a `Plan` domain object.
7.  The `Plan` object is passed to the `ExecutionOrchestrator` (`IRunPlanUseCase`), and the execution proceeds as normal.

## 5. Scope of Work

This checklist provides the ordered, step-by-step implementation plan. Follow the steps sequentially to build the feature using an outside-in, test-driven approach.

### Setup
- [x] Add `mistletoe==1.3.0` to `pyproject.toml` and run `poetry lock && poetry install`.

### Implementation (Outside-In TDD)

1.  **Acceptance Test (Red)**
    -   [ ] CREATE a new failing acceptance test in a new file (`tests/acceptance/test_markdown_plans.py`) for the primary success scenario: executing a simple `.md` plan file that creates a file. This test will fail because the system cannot yet handle `.md` files.

2.  **CLI Adapter (Outermost Layer)**
    -   [ ] READ the design document for the [CLI Adapter](./../adapters/executor/inbound/cli.md).
    -   [ ] IMPLEMENT the Plan Parser Factory logic within the CLI Adapter (`main.py`) as specified in the design. The factory should inspect the input source (file extension or clipboard content) to determine which parser to use. The acceptance test will now fail differently, likely because the `IPlanParser` port or `MarkdownPlanParser` does not exist.

3.  **Core Contracts (Ports)**
    -   [ ] READ the design document for the [IPlanParser Port](./../core/ports/inbound/plan_parser.md).
    -   [ ] IMPLEMENT the `IPlanParser` abstract base class in a new file (`src/teddy_executor/core/ports/inbound/plan_parser.py`).

4.  **Refactor Existing Service**
    -   [ ] READ the design document for the [YamlPlanParser Service](./../core/services/plan_parser.md).
    -   [ ] REFACTOR the existing `PlanParser` to `YamlPlanParser`. This involves renaming the class, the file, and updating it to implement the `IPlanParser` port.
    -   [ ] VERIFY that all existing YAML-based acceptance tests continue to pass without modification.

5.  **Implement New Service (Innermost Layer)**
    -   [ ] READ the design document for the [MarkdownPlanParser Service](./../core/services/markdown_plan_parser.md).
    -   [ ] IMPLEMENT the `MarkdownPlanParser` service in a new file. Ensure it implements the `IPlanParser` port and correctly uses a fence pre-processor and the `mistletoe` library as detailed in the design notes.
    -   [ ] CREATE unit tests for the `MarkdownPlanParser` to verify its AST traversal logic in isolation.

6.  **Acceptance Test (Green)**
    -   [ ] VERIFY that the initial acceptance test created in Step 1 now passes.
    -   [ ] ADD new acceptance tests to cover all action types (`READ`, `EDIT`, `INVOKE`, etc.) as defined in the [New Plan Format Specification](./../specs/new-plan-format.md) to ensure full feature coverage.
