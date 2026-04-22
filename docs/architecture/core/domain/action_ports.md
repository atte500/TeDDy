# Component: ActionPorts
- **Status:** Planned

## Purpose / Responsibility
A data transfer object used to group the collection of outbound ports required by the `ActionFactory`. This prevents constructor bloat (PLR0913) and simplifies the composition root's wiring logic.

## Logic
This is a pure data structure (Dataclass) containing references to port interfaces.

## Data Contracts / Methods
```python
@dataclass(frozen=True)
class ActionPorts:
    shell_executor: IShellExecutor
    file_system_manager: IFileSystemManager
    user_interactor: IUserInteractor
    web_scraper: IWebScraper
    web_searcher: IWebSearcher
    config_service: Optional[IConfigService] = None
```
