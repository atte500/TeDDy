# Application Service: `ContextService`

**Status:** Updated

## 1. Purpose

The `ContextService` is the application service responsible for orchestrating the gathering of project context. It implements the `IGetContextUseCase` inbound port and acts as the central coordinator, using various outbound ports to collect information and assemble it into a `ProjectContext` data transfer object.

It also provides session-aware web content caching to avoid redundant fetches for URLs in repeated context files across turns.

## 2. Used Outbound Ports

*   [`IFileSystemManager`](../ports/outbound/file_system_manager.md): To read `.gitignore`, `.teddyignore` and other context files.
*   [`IRepoTreeGenerator`](../ports/outbound/repo_tree_generator.md): To generate the repository's file tree as a string.
*   [`IEnvironmentInspector`](../ports/outbound/environment_inspector.md): To gather information about the operating system and environment, including the user's shell.
*   [`IWebScraper`](../ports/outbound/web_scraper.md): To fetch and include content from remote URLs included in the context.

## 3. Implemented Inbound Ports

*   [`IGetContextUseCase`](../ports/inbound/get_context_use_case.md)

## 4. Web Content Caching (Session)

The `ContextService` provides intra-session web content caching to avoid redundant HTTP fetches for URLs listed in `session.context` or `turn.context`.

### 4.1 Lifecycle
- **Cache Location:** `<session_root>/.web_cache.json`
- **Format:** Standard JSON dictionary mapping URL (string) to content (string). Written with `ensure_ascii=False` for non-ASCII URLs.
- **Load:** Cache is loaded from disk at the start of each `get_context()` call via `_load_web_cache()`. Missing or corrupt files (invalid JSON, non-dict structure) result in an empty cache (no exception). Handles `OSError` and `json.JSONDecodeError` gracefully.
- **Write:** After each successful `IWebScraper.get_content()` call, the cache dictionary is updated and persisted atomically via `_save_web_cache()`: write to `.web_cache.json.tmp`, then `Path.replace()` to `.web_cache.json`. Creates the cache directory if it does not exist (using `Path.mkdir(parents=True, exist_ok=True)`).
- **No TTL:** Caching is intra-session only. A new session always starts with an empty cache.
- **Failures NOT Cached:** Network errors or exceptions during `get_content()` are never cached, ensuring retries always re-fetch. The error is stored as `None` in `file_contents` but is NOT added to the cache dictionary.
- **Per-Fetch Persistence:** Cache is persisted after EACH successful fetch, not batched at the end, minimizing data loss if the process crashes mid-loop.

### 4.2 Private Methods

#### `_load_web_cache(cache_dir: Optional[str]) -> dict[str, str]`
- Reads and parses the `.web_cache.json` file. Returns an empty dict if the file is missing, contains invalid JSON, or has an incorrect structure.

#### `_save_web_cache(cache_dir: str, cache: dict[str, str]) -> None`
- Writes the cache dictionary to disk atomically. Creates the `cache_dir` if it does not exist. Writes to a `.tmp` file first, then atomically renames to `.web_cache.json` using `Path.replace()`.

### 4.3 Cache Integration in `get_context()`
The cache is integrated into the existing URL-fetching loop inside `get_context()`:
1. Load cache into a local dictionary.
2. For each URL, check the cache dictionary first.
3. If cache hit -> use cached content.
4. If cache miss -> call `IWebScraper.get_content()`, store result in cache dict, persist atomically.
5. If `get_content()` raises -> store `None` in the result dict (failure is NOT cached).

## 5. Failure Modes

- **Missing Directories:** Handled gracefully via `IFileSystemManager` checks.
- **Permission Errors:** Propagated from the adapter layer.
- **Cache Corruption:** Invalid `.web_cache.json` is silently treated as an empty cache. No exception is raised.
- **Backward Compatibility:** When `cache_dir` is `None` (default), no caching occurs, preserving existing behavior for `PlanningService` and `session_cli_handlers` callers.

## 5. Orchestration Logic

When the `get_context` method is called, the `ContextService` performs the following steps in order:

1.  **Recursive Expansion:** It resolves input paths. If a path is a directory, it recursively expands its contents, filtering results through `IRepoTreeGenerator`'s ignore logic to ensure consistency with the visible file tree.

1.  It invokes the `IEnvironmentInspector` to get system information, ensuring the user's `shell` is included.
2.  It invokes the `IRepoTreeGenerator` to get the repository tree as a single string. The generator is responsible for respecting `.gitignore` and `.teddyignore` rules.
3.  It uses the `IFileSystemManager` to read the file paths from all `.teddy/*.context` files. These paths form the `context_vault_paths`.
4.  It uses the `IFileSystemManager` again to read the content of each file in `context_vault_paths`.
5.  It gathers all paths into `ContextItem` DTOs, performing **deduplication** to ensure each unique path appears only once. If a path exists in multiple scopes (e.g., "Session" and "Turn"), it prioritizes non-"Turn" scopes to prevent double-counting in token budget calculations.
6.  It formats the system information into a `header` string and the repository tree and file contents into a `content` string using private helper methods.
7.  It assembles the final `ProjectContext` DTO with the formatted `header`, `content`, and deduplicated `items`, then returns it.

## 5. Data Contracts / Methods

### `get_context(context_files: Optional[Sequence[str]] = None, cache_dir: Optional[str] = None) -> ProjectContext`

-   **Description:** Gathers project context information. Optionally uses a session-level web content cache to avoid redundant URL fetches.
-   **Arguments:**
    -   `context_files`: (Optional) A list of specific `.context` files to read paths from. If `None`, the service defaults to reading all `.context` files in the `.teddy/` root (Standard/Manual mode).
    -   `cache_dir`: (Optional) The path to a session directory where `.web_cache.json` is stored. When provided, web content is cached and reused across turns within the same session.
-   **Returns:** A `ProjectContext` DTO containing the system info, repo tree, and resolved file contents.

## 6. Implementation Notes

-   **Context Configuration:** The `context` command's behavior is explicitly driven by the contents of `.teddy/*.context` files, providing a clear, user-configurable contract.
