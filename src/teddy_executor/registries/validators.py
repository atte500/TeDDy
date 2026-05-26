from __future__ import annotations
import punq


def register_validators(container: punq.Container) -> None:
    """Registers action-specific and plan validators."""
    from teddy_executor.core.ports.outbound import IConfigService, IFileSystemManager
    from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
    from teddy_executor.core.services.plan_validator import PlanValidator
    from teddy_executor.core.services.validation_rules.edit import EditActionValidator
    from teddy_executor.core.services.validation_rules.execute import (
        ExecuteActionValidator,
    )
    from teddy_executor.core.services.validation_rules.filesystem import (
        CreateActionValidator,
        ReadActionValidator,
        PruneActionValidator,
    )
    from teddy_executor.core.services.validation_rules.message import (
        MessageActionValidator,
    )

    container.register(CreateActionValidator, scope=punq.Scope.transient)
    container.register(MessageActionValidator, scope=punq.Scope.transient)
    container.register(
        EditActionValidator,
        factory=lambda: EditActionValidator(
            container.resolve(IFileSystemManager), container.resolve(IConfigService)
        ),
        scope=punq.Scope.transient,
    )
    container.register(ExecuteActionValidator, scope=punq.Scope.transient)
    container.register(ReadActionValidator, scope=punq.Scope.transient)
    container.register(PruneActionValidator, scope=punq.Scope.transient)

    container.register(
        IPlanValidator,
        factory=lambda: PlanValidator(
            container.resolve(IFileSystemManager),
            validators=[
                container.resolve(CreateActionValidator),
                container.resolve(EditActionValidator),
                container.resolve(ExecuteActionValidator),
                container.resolve(ReadActionValidator),
                container.resolve(PruneActionValidator),
                container.resolve(MessageActionValidator),
            ],
        ),
        scope=punq.Scope.transient,
    )
