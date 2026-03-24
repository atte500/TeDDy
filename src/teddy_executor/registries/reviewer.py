from __future__ import annotations
import punq


def register_reviewer(container: punq.Container, ui_mode: str | None = None) -> None:
    """Explicitly registers a reviewer implementation, optionally overriding config."""
    from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer

    if ui_mode is None:
        from teddy_executor.core.ports.outbound import IConfigService

        config = container.resolve(IConfigService)
        ui_mode = config.get_setting("ui_mode", default="tui")

    if ui_mode == "console":
        from teddy_executor.adapters.inbound.console_plan_reviewer import (
            ConsolePlanReviewer,
        )
        from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
        from teddy_executor.core.ports.outbound import (
            IFileSystemManager,
            IUserInteractor,
            IConfigService,
        )

        container.register(
            IPlanReviewer,
            factory=lambda: ConsolePlanReviewer(
                user_interactor=container.resolve(IUserInteractor),
                file_system_manager=container.resolve(IFileSystemManager),
                config_service=container.resolve(IConfigService),
                edit_simulator=container.resolve(IEditSimulator),
            ),
        )
    else:
        from teddy_executor.adapters.inbound.textual_plan_reviewer import (
            TextualPlanReviewer,
        )
        from teddy_executor.core.ports.outbound import (
            IFileSystemManager,
            ISystemEnvironment,
        )

        container.register(
            IPlanReviewer,
            factory=lambda: TextualPlanReviewer(
                system_env=container.resolve(ISystemEnvironment),
                file_system=container.resolve(IFileSystemManager),
            ),
        )
