"""Sandbox replica: the anchoring step forwards configured constructor values.

Copy of ``teddy_executor.__main__._ensure_project_initialized`` with one
change: the re-registrations become lazy factories that supply ``root_dir``
together with the configured tree depth and read cap, so the anchoring step
stops discarding every configured constructor argument.
"""

from __future__ import annotations


def ensure_project_initialized(container, root_dir: str | None = None) -> None:
    """Performs project anchoring while preserving configured values."""
    from punq import Scope

    from teddy_executor.adapters.inbound.cli_helpers import find_project_root
    from teddy_executor.adapters.outbound.local_file_system_adapter import (
        LocalFileSystemAdapter,
    )
    from teddy_executor.adapters.outbound.local_repo_tree_generator import (
        LocalRepoTreeGenerator,
    )
    from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter
    from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
    from teddy_executor.core.ports.inbound.init import IInitUseCase
    from teddy_executor.core.ports.outbound.config_service import IConfigService
    from teddy_executor.core.ports.outbound.file_system_manager import (
        IFileSystemManager,
    )
    from teddy_executor.core.ports.outbound.repo_tree_generator import (
        IRepoTreeGenerator,
    )

    root = root_dir if root_dir is not None else str(find_project_root())
    c = container

    regs = getattr(c.registrations, "_Registry__registrations", {})

    def is_override(service_type) -> bool:
        reg_list = regs.get(service_type)
        return any(
            reg.scope == Scope.singleton or hasattr(reg, "instance")
            for reg in (reg_list or [])
        )

    if not is_override(IConfigService):
        c.register(IConfigService, YamlConfigAdapter, root_dir=root)
    if not is_override(IFileSystemManager):
        c.register(
            IFileSystemManager,
            factory=lambda: LocalFileSystemAdapter(
                edit_simulator=c.resolve(IEditSimulator),
                root_dir=root,
                max_read_lines=c.resolve(IConfigService).get_setting(
                    "read.max_lines"
                ),
            ),
            scope=Scope.transient,
        )
    if not is_override(IRepoTreeGenerator):
        c.register(
            IRepoTreeGenerator,
            factory=lambda: LocalRepoTreeGenerator(
                root_dir=root,
                max_depth=c.resolve(IConfigService).get_setting(
                    "context.max_depth", 0
                ),
            ),
            scope=Scope.transient,
        )

    c.resolve(IInitUseCase).ensure_initialized()