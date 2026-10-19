# Component Design: ContextService
- **Status:** Implemented
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
- [`IWebScraper`](../ports/outbound/web_scraper.md): Fetches remote URL content.
- **`core.utils.markdown` helpers**: Provide fence embedding and session-history naming.

## Class Invariants
- `session_scoped_cache`: Web content is cached in `<session_root>/.web_cache.json` for the session only; no TTL is applied.
- `atomic_cache_write`: The cache is written to a temporary file and renamed with `Path.replace`.
- `failures_not_cached`: A failed fetch is recorded as `None` for the run but never written to the cache.
- `scope_dedup_priority`: A path present in several scopes keeps the non-`Turn` scope.
- `single_git_status_call`: `get_git_status` runs once per turn. Its value feeds the fenced Git Status body, the `ProjectContext.git_status` field, and the badge parser.

## Inbound Ports
- **`IGetContextUseCase`**: Exposes the single `get_context(...)` operation.

## Outbound Ports
- **`IFileSystemManager`**, **`IRepoTreeGenerator`**, **`IEnvironmentInspector`**, **`ILlmClient`**, **`IWebScraper`**: The ports orchestrated during context assembly.

## Data Contracts
- **`ProjectContext`** (`teddy_executor.core.domain.models.project_context`): The assembled aggregate.
- **`ContextItem`** (`teddy_executor.core.domain.models.project_context`): Per-file context metadata.

## Operations

### `get_context(context_files=None, include_tokens=True, agent_name="Unknown", total_window=0, cache_dir=None, current_turn=None, system_prompt_tokens=0) -> ProjectContext`
- **Preconditions:** None.
- **Postconditions:** Returns a `ProjectContext` carrying the header, content, scoped paths, Git status, and per-file items. Remote URLs are fetched in parallel and cached when `cache_dir` is set.
- **Exceptions:** None declared; per-URL fetch failures are recorded as missing content.
