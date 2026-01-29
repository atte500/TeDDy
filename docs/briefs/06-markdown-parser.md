# Architectural Brief: Markdown Plan Parser

## 1. Goal (The "Why")

The strategic goal is to evolve the `teddy` executor's plan format from YAML to Markdown. This change will improve the readability and authoring experience of AI-generated plans, making the system more transparent and user-friendly.

This brief is based on the full specification defined in the [New Plan Format Specification](/docs/specs/new-plan-format.md).

## 2. Proposed Solution (The "What")

To ensure system stability and minimize regression risk, the new Markdown parser will be introduced as an **adapter**. It will conform to the same `IPlanParser` interface as the existing `YamlPlanParser`, consuming a raw string and producing the same `Plan` domain object. This architectural choice decouples the parsing logic from the core execution logic, preserving the validity of our existing test suite.

The implementation will consist of three main components:

1.  **Fence Pre-processor:** A utility will be created to run before the main parser. It will scan the raw LLM output and deterministically correct any invalid nested code block fences (e.g., a ` ``` ` fence inside another ` ``` ` fence). This guarantees that the plan passed to the parser is always valid Markdown. The corrected version will be saved to disk, not the raw output.

2.  **AST-Based Parser:** A new `MarkdownPlanParser` service will be implemented using the `mistletoe` library to parse the pre-processed Markdown into an Abstract Syntax Tree (AST). This approach is more robust and maintainable than regex-based solutions.

3.  **Parser Factory:** The application's composition root (`main.py`) will be updated to include a factory. This factory will inspect the input (e.g., file extension) and inject the correct parser implementation (`MarkdownPlanParser` or `YamlPlanParser`) at runtime, ensuring full backwards compatibility.

## 3. Implementation Analysis (The "How")

The codebase exploration confirms that a new parser can be integrated smoothly by introducing a formal interface and a factory pattern at the application's entry point.

-   **Interface Abstraction:** The current `PlanParser` is a concrete class. To support multiple parser types, a formal `IPlanParser` abstract base class with a single method, `parse(self, plan_content: str) -> Plan`, will be created.
-   **Refactoring:** The existing `PlanParser` will be renamed to `YamlPlanParser` and updated to implement the new `IPlanParser` interface.
-   **Parser Factory Integration:** The `create_container` function in `main.py` is the dependency injection root. However, the choice of parser depends on the runtime input (`.md` vs `.yml` file). Therefore, a factory function will be created and injected. The `execute` command in `main.py` will be modified to detect the plan type and use the factory to request the appropriate parser instance.
-   **Dependency:** The `mistletoe` library will be added as a new project dependency.
-   **Testing Strategy:** The existing test suite for the YAML parser will be adapted to test the refactored `YamlPlanParser`. A new, parallel suite of unit and acceptance tests must be created to validate the `MarkdownPlanParser` and the end-to-end execution of `.md` plans.

## 4. Vertical Slices

This brief will be implemented as a single, comprehensive vertical slice.

-   **[ ] Task: Add Dependencies**
    -   Add `mistletoe==1.3.0` to the `[tool.poetry.dependencies]` section in `pyproject.toml`.

-   **[ ] Task: Refactor Existing Parser**
    -   Create a new abstract base class `IPlanParser` in `core/ports/inbound/plan_parser.py` (or a new file).
    -   In `core/services/plan_parser.py`, rename the existing `PlanParser` class to `YamlPlanParser`.
    -   Update `YamlPlanParser` to inherit from and implement the new `IPlanParser` interface.

-   **[ ] Task: Implement Markdown Parser**
    -   Create a new file for the fence pre-processor utility.
    -   Create `core/services/markdown_plan_parser.py`.
    -   Implement the `MarkdownPlanParser` class, ensuring it conforms to the `IPlanParser` interface. It must use the pre-processor and the `mistletoe` library to parse the plan.

-   **[ ] Task: Integrate via Factory**
    -   In `main.py`, create a `plan_parser_factory` function that takes a file path or content string as input, determines the plan type, and returns an instance of either `YamlPlanParser` or `MarkdownPlanParser`.
    -   Update the `create_container` and `execute` functions to use this factory instead of directly registering a single parser type.

-   **[ ] Task: Handle `INVOKE` Action**
    -   The `MarkdownPlanParser` must correctly parse the `INVOKE` action as defined in the spec.
    -   In `ActionDispatcher`, add a placeholder handler for the `INVOKE` action type that logs a message to the user confirming the action was recognized (e.g., "INVOKE action recognized for agent: [Agent Name]"). Full implementation is out of scope.

-   **[ ] Task: Comprehensive Testing**
    -   Create unit tests for the `MarkdownPlanParser` in isolation.
    -   Create a new suite of acceptance tests for the end-to-end execution of Markdown plans, covering all action types.
    -   Ensure all existing YAML-based acceptance tests continue to pass without modification.
