# Component Design: ActionPorts
- **Status:** Implemented
- **Source:** [`src/teddy_executor/core/domain/models/action_ports.py`](/src/teddy_executor/core/domain/models/action_ports.py)

## Purpose
A frozen data transfer object that groups the collection of outbound ports required by the `ActionFactory`. It prevents constructor parameter bloat and centralizes the action layer's port wiring at the composition root.

## Consumers
- [`ActionFactory`](../services/action_factory.md): Receives an `ActionPorts` instance to build validated actions from raw plan data.
- [Composition Root](/src/teddy_executor/container.py): Constructs the DTO and injects it into `ActionFactory`.

## Dependencies
- [`IShellExecutor`](../ports/outbound/shell_executor.md): Required to execute shell commands.
- [`IFileSystemManager`](../ports/outbound/file_system_manager.md): Required for file create, read, and edit operations.
- [`IUserInteractor`](../ports/outbound/user_interactor.md): Required for user confirmation and free-text input.
- [`IWebScraper`](../ports/outbound/web_scraper.md): Required for fetching remote web content.
- [`IWebSearcher`](../ports/outbound/web_searcher.md): Required for web search queries.
- [`IConfigService`](../ports/outbound/config_service.md): Optional configuration access.

## Class Invariants
- `frozen_dataclass`: The instance is immutable after construction.
- `config_service_optional`: `config_service` defaults to `None` and is the only optional field.

## Inbound Ports
None — this is a passive data structure.

## Outbound Ports
This DTO aggregates, but does not itself consume, the outbound ports listed under Dependencies.

## Data Contracts
- **`ActionPorts`** (frozen dataclass):
    - `shell_executor: IShellExecutor`
    - `file_system_manager: IFileSystemManager`
    - `user_interactor: IUserInteractor`
    - `web_scraper: IWebScraper`
    - `web_searcher: IWebSearcher`
    - `config_service: Optional[IConfigService] = None`

## Operations
None — this component holds data only.
