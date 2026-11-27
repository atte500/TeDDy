# Component Design: FakeAgentCatalog
- **Status:** Implemented
- **Classification:** Test Setup
- **Source:** [`tests/harness/setup/fake_agent_catalog.py`](/tests/harness/setup/fake_agent_catalog.py)

## Purpose
A deterministic in-memory `IAgentCatalog` for reviewer tests. It supplies a roster that is populated, empty, or scripted to fail without reading `.teddy/prompts/`, so a persona-switch case never depends on the workspace it runs in.

## Consumers
- [`TextualPlanReviewer`](../../adapters/inbound/textual_plan_reviewer.md): Receives this double through the app's `agent_catalog` handle, so the System-node switch is drivable against every roster shape.
- [`TestEnvironment`](./test_environment.md): Binds the double under `IAgentCatalog` through `with_agent_catalog`, mirroring the `with_real_*` shape, which is the only way a unit test reaches a container-resolved reviewer with a roster.

## Dependencies
- **`canonical_agent_name`** (`teddy_executor.core.utils.string`): The same normaliser the local adapter applies, so a test never observes a casing the reviewer would not.
- **`_PROMPT_FILES`** (`teddy_executor.core.services.init_service`): The bundled prompt manifest the default roster derives from. It is already the single source of truth the bundled copy and its drift check share, so the double cannot drift from the personas `teddy init prompts` installs.

## Class Invariants
- `same_postconditions_as_the_adapter`: Names are canonicalised, duplicates collapse on first appearance, and the declared order survives, so the double is never kinder than production.
- `no_filesystem_access`: The double never calls `list_prompt_names()`, because that scan resolves `.teddy/prompts/` by walking upward from the process working directory and would make a hermetic reviewer test depend on the checkout.
- `failure_is_explicit`: A scripted error raises before any roster is computed, so "unreadable" and "empty" stay different facts, matching the port's promise.

## Inbound Ports
- **`IAgentCatalog`**: Implements `list_agents() -> tuple[str, ...]`, satisfying the port structurally rather than by inheritance.

## Outbound Ports
None. The double holds its roster in memory and reaches no collaborator at run time.

## Data Contracts
- **`list_agents()` result**: The configured roster, canonicalised and de-duplicated, or `DEFAULT_AGENTS` when none is supplied.
- **`list_calls`**: One entry per listing — the roster that answered, or `None` for a scripted failure — so a test can distinguish never-listed from listed-and-answered from listed-and-failed.
- **`AgentCatalogError`**: The scripted failure the double can raise, which is exactly what the local adapter raises on a listing failure.

## Operations

### `list_agents() -> tuple[str, ...]`
- **Preconditions:** None. The double is usable before any session exists.
- **Postconditions:** Returns the canonical, de-duplicated roster in first-appearance order and appends that roster to `list_calls`.
- **Exceptions:**
  - `AgentCatalogError`: Raised only when the double was constructed with an error, which is how the reviewer's unreadable-roster branch is exercised.
