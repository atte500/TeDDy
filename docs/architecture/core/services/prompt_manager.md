# Component: PromptManager

**Status:** Stable

The `PromptManager` is responsible for resolving agent configurations, system prompts, and metadata for the session audit trail.

## Purpose / Responsibility
The `PromptManager` provides a centralized service for all prompt and metadata resolution. It abstracts the filesystem and internal resources to provide a clean API for other services to retrieve agent-specific logic and user-provided instructions. It is also responsible for extracting telemetry metadata (model, provider, turn cost) from LLM responses and persisting it to the session's `meta.yaml` via the `update_meta` method.

### MRP.xml Base Prompt Injection & Agent Name Injection
Starting in Milestone 3, `fetch_system_prompt()` performs two operations:

1. **Agent Name Injection:** The method now injects the agent name at the very start of the assembled system prompt. The format is: `Agent Name: {AgentName}\n\n` (no leading `#`). The agent name is derived from the `agent_name` parameter (the XML filename stem, e.g., `"architect"` → `"Architect"` with capitalized first letter). This line appears BEFORE any agent-specific XML content.

2. **MRP.xml Appending:** After the agent-specific XML content, the method appends the contents of `MRP.xml` (a bundled resource at `src/teddy_executor/resources/MRP.xml`). MRP.xml is loaded via `importlib.resources` and is NOT copied to `.teddy/prompts/` — it is a protocol-level infrastructure file that must remain unmodified to ensure all agents produce parseable output. The resource root is an additive, optional constructor seam (`mrp_resource_root`, defaulting to the bundled package resource) so tests can inject a real directory without global patching.

The overall return format is: `Agent Name: {Name}\n\n{agent-specific XML}\n\n{MRP content}`.

The injection is NON-breaking: the method signature (`fetch_system_prompt(agent_name, turn_path) -> str`) is unchanged. The return value now contains all three parts.

### Persist-then-reuse (Option A; slice `00-32` Item 2)

As-built, `fetch_system_prompt` is primarily a VERBATIM READER. The composed prompt is persisted at the session root (`{session_root}/{prompt_filename}`) by `SessionService.create_session` at creation and by `SessionService.set_session_agent` on an agent switch; every later turn returns that persisted file UNCHANGED — no header prepend, no MRP append, no content sniffing. The agent-name header and the MRP block are composed only on the LAZY-COMPOSE FALLBACK path (a missing session-root file: a legacy session or a manual delete), which assembles from `.teddy/prompts/` and then persists the result. Because the session-root file IS by definition the composed prompt, no composed-vs-raw disambiguation is required. The injected header's casing is single-sourced through the shared `canonical_agent_name` helper (slice `00-32` Refactor), so the CLI banner, the planning header and the composed prompt header can never drift apart. The legacy `<response_format>` skip lives in the lazy-compose step, keeping the verbatim reader trivial.

### Provider Extraction
After each LLM completion, `update_meta` extracts the resolved downstream provider from `response._hidden_params["provider"]` (populated by litellm). This reflects the actual provider that served the request (e.g., `"deepseek"`, `"together"`, `"openai"`), as opposed to the user-configured provider hint. The extraction uses `getattr(response, "_hidden_params", {}).get("provider", "unknown")` for graceful degradation when `_hidden_params` is absent (e.g., local models).

## Instruction Resolution (Pure Context Model)
In the "Pure Context" model, `PromptManager` does NOT provide instructions for the AI's LLM calls. Its role in message resolution is strictly metadata-focused:
- **Audit Trail Resolution:** It resolves the `user_request` (feedback or CLI message) to ensure it is accurately captured in the `ExecutionReport` and `meta.yaml`.
- **Report Seeding:** This metadata ensures the `ExecutionReportAssembler` can generate a `report.md` that correctly documents the user's intent for the turn, which the AI will then "discover" as context in the subsequent turn.
- **Goal Persistence:** It manages the retrieval of the immutable session goal (`initial_request.md`) from the session root.

## Failure Modes
- **MRP.xml Missing From Resources**: Violates the postcondition "Returns a valid assembled system prompt containing both agent XML and MRP protocol rules." If MRP.xml is absent from `src/teddy_executor/resources/`, `fetch_system_prompt()` MUST raise a clear exception rather than returning a prompt without the MRP rules. This prevents silent protocol degradation.
- **Agent XML Not Found**: If no prompt file is found for the requested agent (searched session root → .teddy/prompts/), `fetch_system_prompt()` returns an empty string. This is logged as a warning but does not raise — useful for graceful degradation during test/development.

## Ports
- **Implements Outbound Port:** [`IPromptManager`](../ports/outbound/prompt_manager.md)
- **Uses Outbound Ports:**
    - `IFileSystemManager` (to read prompt XMLs and meta YAMLs)
    - `IUserInteractor` (to prompt for instructions if missing)
- **Contract Dependencies:**
    - Relies on `importlib.resources` to load MRP.xml from the bundled package. This is NOT done through `IFileSystemManager` — MRP.xml is a true resource, not a user-editable file.

## Contracts / Methods

### `fetch_system_prompt(agent_name, turn_path) -> str`
- **Preconditions:** `agent_name` must be a non-empty string. `turn_path` must be a valid `Path`.
- **Postconditions:** Returns the assembled system prompt. The prompt consists of: (1) a header line `Agent Name: {CapitalizedAgentName}\n\n` (no leading `#`), (2) the agent-specific XML content resolved from the filesystem hierarchy (session root → .teddy/prompts/), followed by (3) the MRP.xml base prompt content loaded via `importlib.resources` — appended ONLY when the resolved agent content does NOT already contain `<response_format>` (legacy user-override detection). Ensures the final prompt starts with the agent name and contains both the agent instructions and the shared MRP protocol rules. If MRP.xml is missing and must be appended, a specific `FileNotFoundError` is raised.
- **Exceptions:**
  - `FileNotFoundError`: If MRP.xml is missing from `src/teddy_executor/resources/`. This is a fatal error that must propagate.
  - No exception is raised if the agent XML is missing — returns empty string with a warning log.
- **Invariants:** The agent name header is always first whenever an agent prompt resolves. The MRP rules are appended AFTER the agent-specific content when the resolved prompt does not already carry `<response_format>`. The method NEVER modifies the agent XML content itself.
