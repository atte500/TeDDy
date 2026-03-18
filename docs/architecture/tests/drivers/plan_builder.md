# Test DSL: MarkdownPlanBuilder
- **Status:** Implemented

## 1. Purpose / Responsibility
Acting as the **Driver** in the Test Harness Triad, the `MarkdownPlanBuilder` is a fluent interface designed to simplify the creation of complex, multi-action Markdown plans in tests. It abstracts the boilerplate of Markdown formatting (headers, rationale, code block fences) and ensures that generated plans adhere to the TeDDy protocol.

## 2. Ports
- **Primary Driving Adapter:** Used by Acceptance and Integration tests to drive the `IPlanParser` and `IRunPlanUseCase`.

## 3. Implementation Details / Logic
- **Fluent API:** Methods return `self` to allow chaining (`.add_action(...).build()`).
- **Deterministic Rationale:** Generates a consistent, minimal rationale section to satisfy parser requirements without cluttering test code.
- **Action Formatting:** Encapsulates the specific Markdown syntax for each action type (`CREATE`, `EDIT`, `EXECUTE`, etc.), including the correct use of backticks for nested code blocks.

## 4. Data Contracts / Methods
- `__init__(title: str)`: Initializes the builder with the plan's H1 title. Automatically generates a valid TeDDy header and default rationale.
- `add_create(path: str, content: str, overwrite: bool = False, description: str = "Creating file") -> self`: Implements `CREATE`. Automatically formats the root-relative link for the path.
- `add_read(resource: str, description: str = "Reading resource") -> self`: Implements `READ`. Automatically formats the root-relative link for the resource.
- `add_edit(path: str, find_replace: Union[str, List[Tuple[str, str]]], replace: str = None, description: str = "Editing file", replace_all: bool = False) -> self`: Implements `EDIT`. Supports single or multiple FIND/REPLACE pairs.
- `add_execute(command: str, description: str = "Running command", expected_outcome: str = "Success", allow_failure: bool = False, background: bool = False, timeout: int = None) -> self`: Implements `EXECUTE`. Handles shell-chaining and protocol flags.
- `add_research(queries: list[str], description: str = "Searching web") -> self`: Implements `RESEARCH`. Groups queries into code blocks per the spec.
- `add_prompt(message: str, reference_files: list[str] = None) -> self`: Implements `PROMPT`.
- `add_invoke(agent: str, description: str, reference_files: list[str] = None) -> self`: Implements `INVOKE`.
- `add_return(description: str, reference_files: list[str] = None) -> self`: Implements `RETURN`.
- `add_prune(resource: str, description: str = "Pruning resource") -> self`: Implements `PRUNE`.
- `build() -> str`: Renders the accumulated actions into a valid Markdown plan string, ensuring correct backtick nesting for all fenced blocks.
