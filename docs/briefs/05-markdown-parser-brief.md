# Architectural Brief: Markdown Plan Parser

## 1. Goal (The "Why")

The strategic goal is to evolve the `teddy` executor's plan format from YAML to Markdown, as specified in `docs/specs/new-plan-format.md`. This change is intended to improve the readability and authoring experience of AI-generated plans, making the system more transparent and user-friendly.

### Core System Requirements:
-   **Format Compliance:** The system must parse all components defined in the new spec.
-   **Strict Error Handling:** The system must provide descriptive errors on malformed input to support AI self-correction.
-   **Functional Equivalence:** The system must support all existing input methods, including file-based and clipboard-based execution.

## 2. Architectural Approach (The "What")

### The Parser as an Adapter
To ensure system stability and minimize regression risk, the new Markdown parser will be introduced as an **adapter**. It will conform to the same `IPlanParser` interface as the existing `YamlPlanParser`, consuming a raw string and producing the same `Plan` domain object.

This architectural choice is critical because it **decouples the parsing logic from the core execution logic**. The `ExecutionOrchestrator` and all downstream services will remain unchanged, ensuring that our existing, robust test suite remains valid.

### Selected Technology
A technical spike has validated the use of the `mistletoe` library for parsing the Markdown into an Abstract Syntax Tree (AST). This approach was chosen over regex-based or specialized data-extraction libraries due to its superior robustness, flexibility, and long-term maintainability.

## 3. Key Architectural Considerations (The "How")

This section outlines the high-level considerations for the Architect to incorporate into a detailed technical design.

-   **Interface Definition:** The new `MarkdownPlanParser` must share a common interface with `YamlPlanParser` (e.g., an abstract base class or a structural contract) to ensure they are interchangeable.
-   **Parser Factory:** The composition root (in `main.py`) should implement a factory pattern. This factory will be responsible for inspecting the input (e.g., file extension or content heuristics) and injecting the correct parser implementation (`MarkdownPlanParser` or `YamlPlanParser`) at runtime.
-   **Backwards Compatibility:** The `YamlPlanParser` must be preserved to ensure full backwards compatibility for existing workflows and test cases. The system should be designed to handle both formats seamlessly.
-   **Testing Strategy:**
    -   The existing acceptance test suite, which relies on YAML plans, must continue to pass without modification.
    -   New unit tests should be created to validate the `MarkdownPlanParser`'s logic in isolation.
    -   New acceptance tests must be added to verify the end-to-end execution of plans originating from `.md` files. A key test will be to prove that a logical plan expressed in both YAML and Markdown results in identical system behavior.
-   **Dependency Management:** The introduction of the `mistletoe` library must be documented, and its impact on the project's dependency graph should be reviewed.
-   **Implementation Slice:** Per the final strategic decision, this feature will be implemented as a single, comprehensive vertical slice. The Architect's plan should incorporate the following tasks in a logical, dependency-aware order:
    -   [ ] **Dependency Management:** Add `mistletoe==1.3.0` as a project dependency.
    -   [ ] **Core Service Implementation:** Create and implement the `MarkdownPlanParser` service. It must be capable of parsing a `plan.md` file and all its components (header, context vault, all action types) into a `Plan` domain object, mirroring the interface of the existing `YamlPlanParser`.
    -   [ ] **Integration:** Update the factory in `main.py` to recognize and delegate Markdown plans to the new parser, while preserving the existing `YamlPlanParser` for backwards compatibility.
    -   [ ] **Comprehensive Testing:**
        -   Develop unit tests for the `MarkdownPlanParser` in isolation.
        -   Create a new suite of acceptance tests for the end-to-end execution of Markdown plans, covering all action types (`READ`, `RESEARCH`, `CREATE`, `EDIT`, `EXECUTE`, `CHAT_WITH_USER`, `INVOKE`).
        -   Ensure existing YAML-based acceptance tests continue to pass.
    -   [ ] **Special Handling for `INVOKE` Action:** The `INVOKE` action is a new type defined in the spec with no existing handler. For this implementation slice, a full handler is **out of scope**. The parser must correctly identify and parse the `INVOKE` action's data. However, the execution logic should be a simple placeholder that logs a message to the user confirming that the action was parsed (e.g., "INVOKE action recognized for agent: [Agent Name]").
