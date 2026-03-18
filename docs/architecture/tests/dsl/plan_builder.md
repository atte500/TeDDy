# Test DSL: MarkdownPlanBuilder
- **Status:** Implemented
- **Introduced in:** [Slice 09-01](../../../project/slices/09-01-test-harness-blueprinting.md)

## 1. Purpose / Responsibility
The `MarkdownPlanBuilder` is a fluent interface designed to simplify the creation of complex, multi-action Markdown plans in tests. It abstracts the boilerplate of Markdown formatting (headers, rationale, code block fences) and ensures that generated plans adhere to the TeDDy protocol.

## 2. Ports
- **Primary Driving Adapter:** Used by Acceptance and Integration tests to drive the `IPlanParser` and `IRunPlanUseCase`.

## 3. Implementation Details / Logic
- **Fluent API:** Methods return `self` to allow chaining (`.add_action(...).build()`).
- **Deterministic Rationale:** Generates a consistent, minimal rationale section to satisfy parser requirements without cluttering test code.
- **Action Formatting:** Encapsulates the specific Markdown syntax for each action type (`CREATE`, `EDIT`, `EXECUTE`, etc.), including the correct use of backticks for nested code blocks.

## 4. Data Contracts / Methods
- `__init__(title: str)`: Initializes the builder with the plan's H1 title.
- `add_action(action_type: str, params: dict, content_blocks: dict = None) -> MarkdownPlanBuilder`: Adds a structured action to the internal list.
- `build() -> str`: Renders the accumulated actions into a valid Markdown plan string.
