# Component Design: ActionPorts
- **Status:** Implemented
- **Classification:** Core Domain
- **Source:** [`src/teddy_executor/core/domain/models/action_ports.py`](/src/teddy_executor/core/domain/models/action_ports.py)

## Purpose
A frozen data transfer object that groups the collection of outbound ports required by the `ActionFactory`. It prevents constructor parameter bloat and centralizes the action layer's port wiring at the composition root.

## Consumers
- [`ActionFactory`](../services/action_factory.md): Receives an `ActionPorts` instance to build validated actions from raw plan data. The remote READ's cached-fetch coordinator arrives as a separate constructor keyword, because this DTO carries outbound ports only and a `core/domain/models/` type must not name a `core/services/` class.
- [Composition Root](/src/teddy_executor/container.py): Constructs the DTO and injects it into `ActionFactory`.

## Dependencies
- [`IShellExecutor`](../ports/outbound/shell_executor.md): Required to execute shell commands.
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Required for file create, read, and edit operations.
- [`IUserInteractor`](../ports/outbound/user_interactor.md): Required for user confirmation and free-text input.

- [`IWebSearcher`](../ports/outbound/web_searcher.md): Required for web search queries.
- [`IConfigService`](../ports/outbound/config_service.md): Optional configuration access.
- [`IPdfExtractor`](../ports/outbound/pdf_extractor.md): Optional PDF text extraction for a PDF `READ`.

## Class Invariants
- `frozen_dataclass`: The instance is immutable after construction.
- `optional_defaults_none`: `config_service` and `pdf_extractor` both default to `None`, so an assembly site that omits them keeps the non-configurable and text-only paths working.
- `no_scraper_handle`: The bundle carries no web scraper, because the remote READ binds the cache-aware coordinator instead. A scraper field here would be a second, uncached path to the same capability.

## Inbound Ports
None — this is a passive data structure.

## Outbound Ports
This DTO aggregates, but does not itself consume, the outbound ports listed under Dependencies.

## Data Contracts
- **`ActionPorts`** (frozen dataclass):
    - `shell_executor: IShellExecutor`
    - `file_system_manager: IFileSystemManager`
    - `user_interactor: IUserInteractor`
    - `web_searcher: IWebSearcher`
    - `config_service: Optional[IConfigService] = None`
    - `pdf_extractor: Optional[IPdfExtractor] = None`

## Operations
None — this component holds data only.
