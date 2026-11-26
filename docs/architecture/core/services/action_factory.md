# Component Design: ActionFactory
- **Status:** Implemented
- **Classification:** Core Service
- **Source:** [`src/teddy_executor/core/services/action_factory.py`](/src/teddy_executor/core/services/action_factory.py)

## Purpose
Translates an action type string from a plan into an executable `IAction` handler. It binds the correct method of an injected outbound port adapter to the uniform `execute(**kwargs)` interface and injects configuration-driven defaults.

## Consumers
- [`ActionDispatcher`](./action_dispatcher.md): Receives the factory through the `IActionFactory` protocol to create action handlers.
- [Composition Root](/src/teddy_executor/container.py): Constructs the factory from an `ActionPorts` DTO.

## Dependencies
- [`ActionPorts`](../domain/action_ports.md): The DTO that groups the outbound ports.
- [`IShellExecutor`](../ports/outbound/shell_executor.md): Supplies the EXECUTE handler.
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Supplies the CREATE, EDIT, and local READ handlers.
- [`IUserInteractor`](../ports/outbound/user_interactor.md): Supplies the MESSAGE handler.
- [`WebContentService`](./web_content_service.md): Supplies the remote READ handler, owning the cached fetch, the verbatim store, and the announced cap. Injected as a constructor keyword beside `ports`, not through `ActionPorts`, because it is a core service rather than an outbound port.
- [`IWebSearcher`](../ports/outbound/web_searcher.md): Supplies the RESEARCH handler.
- [`IConfigService`](../ports/outbound/config_service.md): Supplies the default timeout, similarity threshold, and the `read.max_lines` budget.
- [`IPdfExtractor`](../ports/outbound/pdf_extractor.md): Supplies the local PDF extraction behind a PDF `READ`.
- **`DEFAULT_SIMILARITY_THRESHOLD`** (`teddy_executor.core.domain.models.plan`): The fallback similarity threshold.

## Class Invariants
- `ports_from_dto`: Every outbound port arrives through the `ActionPorts` DTO; the factory holds no container reference.
- `read_polymorphism`: The READ action is routed by resource type (remote URL, PDF source, line-range request, or local file) to a distinct handler.
- `pdf_precedes_lines`: A PDF source is routed before the line-range branch, so a `lines` range on a PDF is ignored and the full text is extracted.
- `pdf_cap_resolved_once`: The PDF handler resolves `read.max_lines` at action-creation time and applies the shared head-truncation helper, so a PDF obeys the same budget as a text file.
- `config_default_injection`: When a plan omits `timeout` or `similarity_threshold`, the factory injects the configured default.
- `remote_read_through_coordinator`: A READ on an `http`/`https` resource binds `WebContentService.fetch_one` with the `session_root` known at creation time, so the handler never touches the scraper and never decides truncation itself.
- `absent_scope_still_reads`: A creation call without a `session_root` still performs the READ, uncached, because a plan outside a session still has to fetch.

## Inbound Ports
None — the factory is a concrete service consumed through the `IActionFactory` protocol.

## Outbound Ports
- **`IShellExecutor`**, **`IFileSystemManager`**, **`IUserInteractor`**, **`IWebSearcher`**, **`IConfigService`**: The port methods bound to action handlers.
- **`WebContentService`**: The collaborator whose `fetch_one` the remote READ handler binds.

## Data Contracts
- **`ActionPorts`** (`teddy_executor.core.domain.models.action_ports`): The injected port bundle.
- **`IAction`** (`teddy_executor.core.services.action_dispatcher`): The handler protocol exposing `execute(**kwargs)`.

## Operations

### `create_action(action_type, params=None, session_root=None) -> IAction`
- **Preconditions:** `action_type` is a known verb.
- **Postconditions:** Returns an `IAction` whose `execute` calls the mapped adapter method. A remote READ binds `WebContentService.fetch_one` with the creation-time `session_root`, returning the body capped at `read.max_lines` with the announced notice; a PDF READ binds `IFileSystemManager.read_file_bytes` and then `IPdfExtractor.extract_text`, capped at `read.max_lines` when configured; a line-range READ binds `IFileSystemManager.read_raw_file`; a local READ binds `IFileSystemManager.read_file`.
- **Exceptions:**
  - `ValueError`: Unknown or unmapped action verb provided.
  - `AssertionError`: A PDF READ is created while `ActionPorts.pdf_extractor` is `None`, which is a composition-root defect rather than user input.
