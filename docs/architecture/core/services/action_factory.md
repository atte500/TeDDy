# Component Design: ActionFactory
- **Status:** Implemented
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
- [`IWebScraper`](../ports/outbound/web_scraper.md): Supplies the remote READ handler.
- [`IWebSearcher`](../ports/outbound/web_searcher.md): Supplies the RESEARCH handler.
- [`IConfigService`](../ports/outbound/config_service.md): Supplies the default timeout and similarity threshold.
- **`DEFAULT_SIMILARITY_THRESHOLD`** (`teddy_executor.core.domain.models.plan`): The fallback similarity threshold.

## Class Invariants
- `ports_from_dto`: Every outbound port arrives through the `ActionPorts` DTO; the factory holds no container reference.
- `read_polymorphism`: The READ action is routed by resource type (remote URL, line-range request, or local file) to a distinct handler.
- `config_default_injection`: When a plan omits `timeout` or `similarity_threshold`, the factory injects the configured default.

## Inbound Ports
None — the factory is a concrete service consumed through the `IActionFactory` protocol.

## Outbound Ports
- **`IShellExecutor`**, **`IFileSystemManager`**, **`IUserInteractor`**, **`IWebScraper`**, **`IWebSearcher`**, **`IConfigService`**: The port methods bound to action handlers.

## Data Contracts
- **`ActionPorts`** (`teddy_executor.core.domain.models.action_ports`): The injected port bundle.
- **`IAction`** (`teddy_executor.core.services.action_dispatcher`): The handler protocol exposing `execute(**kwargs)`.

## Operations

### `create_action(action_type, params=None) -> IAction`
- **Preconditions:** `action_type` is a known verb.
- **Postconditions:** Returns an `IAction` whose `execute` calls the mapped adapter method. A remote READ binds `IWebScraper.get_content`; a line-range READ binds `IFileSystemManager.read_raw_file`; a local READ binds `IFileSystemManager.read_file`.
- **Exceptions:** `ValueError` when the action type is unknown.
