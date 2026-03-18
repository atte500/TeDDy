# Slice 09-01: Test Harness Blueprinting
- **Status:** Planned
- **Milestone:** [Milestone 09: Hexagonal Test Architecture](../milestones/09-hexagonal-test-architecture.md)
- **Specs:** N/A

## 1. Business Goal
Establish the formal architectural blueprint for the TeDDy test harness. By treating the test suite as a Primary Driving Adapter and documenting its components (DSLs, Object Mothers, Contexts), we create the necessary infrastructure to support strict, unified code quality guardrails (300 SLOC limit) across the entire codebase.

## 2. Acceptance Criteria (Scenarios)

### Scenario 1: Establish Test Boundary & Layers
**Goal:** Formally define the "tests" boundary and its internal layers in the project's central architecture document.
- **Precondition:** `ARCHITECTURE.md` only covers production boundaries.
- **Success Condition:** `ARCHITECTURE.md` includes a "Test Boundary" section with layers for `dsl`, `builders`, and `contexts`.
- **Success Condition:** The "Component & Boundary Map" includes a table for Test Harness components.
#### Deliverables
- [x] Updated [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) with Test Boundary definitions.

### Scenario 2: Document Core Test DSLs & Builders
**Goal:** Create formal design documents for existing test utilities to establish their contracts.
- **Precondition:** Utilities like `plan_builder.py` exist but lack formal design documentation.
- **Success Condition:** Design documents exist in `docs/architecture/tests/` for `PlanBuilder` and any identified `ObjectMothers`.
- **Success Condition:** Each document defines clear Ports (how they drive the system) and Data Contracts.
#### Deliverables
- [x] Design Document: [MarkdownPlanBuilder](../architecture/tests/dsl/plan_builder.md).
- [x] Design Document: [CliTestAdapter](../architecture/tests/adapters/cli_adapter.md).

### Scenario 3: Define "Test Context" Pattern
**Goal:** Establish a standard pattern for "Test Contexts" to encapsulate complex setup and state management for acceptance/integration tests.
- **Precondition:** Acceptance tests often use ad-hoc setup logic.
- **Success Condition:** A design document for a `TestContext` component is created, providing a template for future test refactoring.
#### Deliverables
- [x] Design Document: [Test Composition](../architecture/tests/contexts/composition.md).

## 3. Architectural Changes
The testing suite is promoted to a formal architectural boundary. This change introduces a clear hierarchy: Tests -> Test DSL -> Test Adapter -> System.

- **New Boundary:** `tests` (documented in `ARCHITECTURE.md`).
- **Layers:**
    - `dsl`: Fluent builders for domain-specific inputs (e.g., [MarkdownPlanBuilder](../architecture/tests/dsl/plan_builder.md)).
    - `adapters`: Specialized drivers for the system's primary inbound ports (e.g., [CliTestAdapter](../architecture/tests/adapters/cli_adapter.md)).
    - `contexts`: Orchestrators for complex test setup and DI container management.

## 4. Interaction Sequence
1.  **Test Case:** Invokes the `MarkdownPlanBuilder` to define the desired state.
2.  **PlanBuilder:** Returns a valid Markdown string.
3.  **Test Case:** Passes the string to the `CliTestAdapter`.
4.  **CliTestAdapter:** Executes the command in-process, captures output, and uses the `ReportParser` to return a structured dict.
5.  **Test Case:** Performs assertions against the structured dict.
