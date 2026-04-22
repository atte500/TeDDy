from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from teddy_executor.core.ports.outbound import (
        IShellExecutor,
        IFileSystemManager,
        IUserInteractor,
        IWebScraper,
        IWebSearcher,
        IConfigService,
    )


@dataclass(frozen=True)
class ActionPorts:
    """
    A data transfer object used to group the collection of outbound ports
    required by the ActionFactory.
    """

    shell_executor: IShellExecutor
    file_system_manager: IFileSystemManager
    user_interactor: IUserInteractor
    web_scraper: IWebScraper
    web_searcher: IWebSearcher
    config_service: Optional[IConfigService] = None
