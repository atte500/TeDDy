from __future__ import annotations
import punq


def register_reviewer(container: punq.Container) -> None:
    """Registers the Textual TUI reviewer unconditionally.

    Console mode has been deprecated, so the Textual TUI is the sole plan
    reviewer. No configuration key can select an alternative reviewer.
    """
    from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
    from teddy_executor.core.ports.outbound import (
        IFileSystemManager,
        ISystemEnvironment,
        IWebScraper,
    )
    from teddy_executor.adapters.outbound.console_tooling import (
        ConsoleToolingHelper,
    )
    from teddy_executor.core.services.action_dispatcher import ActionDispatcher

    def tui_factory():
        from teddy_executor.adapters.inbound.textual_plan_reviewer import (
            TextualPlanReviewer,
        )

        return TextualPlanReviewer(
            system_env=container.resolve(ISystemEnvironment),
            file_system=container.resolve(IFileSystemManager),
            console_tooling=container.resolve(ConsoleToolingHelper),
            action_dispatcher=container.resolve(ActionDispatcher),
            web_scraper=container.resolve(IWebScraper),
        )

    container.register(IPlanReviewer, factory=tui_factory)
