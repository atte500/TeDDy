# Component Design: ContextService
- **Status:** Implemented
- **Classification:** Core Service
- **Source:** [`src/teddy_executor/core/services/context_service.py`](/src/teddy_executor/core/services/context_service.py)

## Purpose
Implements the `IGetContextUseCase` inbound port. It orchestrates the outbound ports to gather system information, the repository tree, and file contents, and assembles them into a single `ProjectContext` payload.

## Consumers
- [CLI Adapter](../../adapters/inbound/cli.md): Gathers context for the `context` command and for session startup.
- [Composition Root](/src/teddy_executor/container.py): Constructs the service and injects its ports.

## Dependencies
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Reads context manifests and file contents.
- [`IRepoTreeGenerator`](../ports/outbound/repo_tree_generator.md): Produces the project file tree.
- [`IEnvironmentInspector`](../ports/outbound/environment_inspector.md): Supplies system information and Git status.
- [`ILlmClient`](../ports/outbound/llm_client.md): Counts tokens for the assembled content.
- [`WebContentService`](./web_content_service.md): Resolves the payload's remote URL bodies through one batched cached fetch, so assembly owns no fetch, cache, or truncation mechanics of its own.
- [`IConfigService`](../ports/outbound/config_service.md): Optional handle that resolves `plan.max_lines` for the plan-content cap and `read.max_lines` for the extracted-PDF cap; a `None` handle falls back to each setting's schema default.
- [`IPdfExtractor`](../ports/outbound/pdf_extractor.md): Optional handle that turns a local PDF resource's raw bytes into its text layer before embedding. A `None` handle is only rejected when a PDF is actually in scope.
- **`core.utils.markdown` helpers**: Provide fence embedding, session-history naming, and the shared `is_own_session_path` / `is_session_history_path` root gate.

## Class Invariants
- `url_scope_delegated`: Every remote URL is resolved by exactly one `WebContentService.fetch_many` call per assembly, so the cache filename, the atomic write, the merge lock, and the parallel fetch pool all live outside this service. A URL already cached is served without a network round trip, and a `None` `session_root` leaves every fetch uncached.
- `url_failure_renders_missing`: A URL whose fetch raised arrives as `None` and renders the same `--- FILE NOT FOUND ---` marker a missing local file receives. Nothing about that failure is persisted, so the next assembly retries it.
- `url_body_embeds_verbatim`: A remote body is embedded exactly as stored, never capped by this service, because the cache holds the untruncated text a later turn must reproduce.
- `scope_dedup_priority`: A path present in several scopes keeps the non-`Turn` scope.
- `session_mode_partition`: In session mode a non-`Turn` path that is not this session's own history renders under `## Session Resources`; a session-scoped path that is this session's own history renders under `## Session History` in chronological order; every remaining path renders under `## Resource Contents`. A path present in several scopes keeps its non-`Turn` destination and renders once.
- `session_sections_root_gated`: Both session-mode sections require a `session_root` in scope, so a `None` root skips the hoist and the history partition alike. A session-agnostic export therefore renders every resource under `## Resource Contents`, a `.teddy/sessions/` path included: there is no history to append to, and the export contract carries no session section. A section is omitted when its path list is empty, so an empty heading never renders.
- `runtime_closes_payload`: `get_context` appends `## Runtime` and exactly the three volatile rows after `_format_content` returns, and `_format_header` emits only the constant environment rows, keeping every byte ahead of the tail byte-stable between turns.
- `content_section_order`: The `content` body renders in one declared order — `CONTENT_SECTION_ORDER` over the `PayloadSection` enum (Session Resources, Session History, Git Status, Project Structure, Resource Contents). A future section is inserted in that declaration with its renderer, never spliced into a call site.
- `falsy_scope_map_triggers_defaults`: A falsy `context_files` value falls back to the `.teddy/*.context` glob. A supplied scope map resolves exactly the scopes it names, with no glob fallback.
- `single_git_status_call`: `get_git_status` runs once per turn. Its value feeds the fenced Git Status body, the `ProjectContext.git_status` field, and the badge parser.
- `plan_cap_truncate_first`: `plan.md` content is capped at `plan.max_lines` in the `file_contents` map before both `_format_content` (the embed) and `_get_path_to_tokens` (the token count), so the embedded window and the pruning `token_count` both reflect the capped length. Only paths ending in `plan.md` are capped; other files and not-found entries pass through unchanged.
- `effective_model_token_count`: Every `get_text_token_count` call counts with the caller-supplied effective model when one is present; an omitted model keeps the single-argument no-model call shape, so existing callers stay valid.
- `pdf_resource_extracts_before_embed`: A local path matched by `is_pdf_source` never reaches `read_files_in_vault`. It is read with `read_file_bytes` and embedded as `IPdfExtractor.extract_text(data, source=path)` output capped at `read.max_lines`, so context assembly never decodes PDF bytes as UTF-8. The vault read still runs exactly once, carrying the remaining text paths (an empty list when the scope holds only PDFs), so a text-only scope behaves byte-identically to before.
- `pdf_not_found_marker`: A PDF path whose `read_file_bytes` raises `FileNotFoundError` maps to `None`, so it renders the same `--- FILE NOT FOUND ---` marker as a missing text resource.
- `pdf_extractor_contract`: `_read_pdf_contents` asserts the injected `IPdfExtractor` is present before extracting, naming the port in the message. A `None` handle therefore fails loudly instead of silently falling back to a raw text read, which is the defect this behaviour replaced.
- `max_lines_resolution_shared`: `_resolve_plan_max_lines` and `_resolve_read_max_lines` both delegate to one `_resolve_max_lines(setting_key, default)`, so the plan and read budgets cannot drift apart in their fallback handling.

## Inbound Ports
- **`IGetContextUseCase`**: Exposes the single `get_context(...)` operation.

## Outbound Ports
- **`IFileSystemManager`**, **`IRepoTreeGenerator`**, **`IEnvironmentInspector`**, **`ILlmClient`**: The ports orchestrated during context assembly.
- **`WebContentService`**: A core service rather than a port, asked once per assembly for the payload's remote URL bodies.
- **`IPdfExtractor`**: Extracts a local PDF resource's text layer so it can be embedded without a text decode. **`IConfigService`** stays optional and resolves both caps.

## Data Contracts
- **`ProjectContext`** (`teddy_executor.core.domain.models.project_context`): The assembled aggregate.
- **`ContextItem`** (`teddy_executor.core.domain.models.project_context`): Per-file context metadata.
- **`PayloadSection`** (`teddy_executor.core.services.context_service`): The enumeration of payload body section names, paired with `CONTENT_SECTION_ORDER`, the single declaration of the body's section order.
- **Project Structure subtitle:** `_format_content` renders the italic line `*Tree capped at depth {max_depth} and {max_children} entries per subdirectory: truncated directories show entry counts only.*` between the `## Project Structure` heading and the opening fence. Both limits come from the `IRepoTreeGenerator` properties, so the section states them once above the compact notices.

## Operations

### `get_context(context_files=None, include_tokens=True, agent_name="Unknown", total_window=0, current_turn=None, system_prompt_tokens=0, session_root=None, model=None) -> ProjectContext`
- **Preconditions:** None.
- **Postconditions:** Returns a `ProjectContext` carrying the header, content, scoped paths, Git status, and per-file items. Each scope expands `.context` manifests, directories, and URLs before deduplication. The Project Structure section names both tree limits once in an italic subtitle between the heading and the fence. Remote URLs are resolved by one batched cached fetch keyed by `session_root`: cached bodies embed verbatim, misses are fetched in parallel and stored, and a URL whose fetch failed renders as missing without being persisted. Any `plan.md` content is capped at `plan.max_lines` before both embedding and token counting, so the embedded plan and its item `token_count` track the cap while the on-disk file stays full. Session history is recognized only under the supplied `session_root`; a session-scoped path that is not this session's own history renders under `## Session Resources`, while a file read from another session is a resource, not our history. A local path named by `is_pdf_source` is embedded as its extracted text layer capped at `read.max_lines` instead of being read verbatim, so a PDF registered by an earlier READ survives assembly rather than crashing the payload with a UTF-8 decode error. The body renders in the single declared `CONTENT_SECTION_ORDER`, and `## Runtime` closes the payload with the three volatile rows regardless of session scope. Every token count (the assembled content and each file) runs against `model` when supplied; an omitted model keeps the provider's configured model.
- **Exceptions:** None declared; per-URL fetch failures are recorded as missing content.
