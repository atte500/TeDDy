from teddy_executor.core.domain.models import ContextResult
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound.file_system_manager import FileSystemManager
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator
from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)


class ContextService(IGetContextUseCase):
    """
    Application service for orchestrating the gathering of project context.
    """

    def __init__(
        self,
        file_system_manager: FileSystemManager,
        repo_tree_generator: IRepoTreeGenerator,
        environment_inspector: IEnvironmentInspector,
    ):
        self._file_system_manager = file_system_manager
        self._repo_tree_generator = repo_tree_generator
        self._environment_inspector = environment_inspector

    def get_context(self) -> ContextResult:
        """
        Gathers all project context information by orchestrating its dependencies.
        """
        # Scenario 2: Simplified Default Configuration
        if not self._file_system_manager.path_exists(".teddy/perm.context"):
            self._file_system_manager.create_default_context_file()

        # Gather all information from outbound ports
        system_info = self._environment_inspector.get_environment_info()
        repo_tree = self._repo_tree_generator.generate_tree()
        context_vault_paths = self._file_system_manager.get_context_paths()
        file_contents = self._file_system_manager.read_files_in_vault(
            context_vault_paths
        )

        # Assemble and return the DTO
        return ContextResult(
            system_info=system_info,
            repo_tree=repo_tree,
            context_vault_paths=context_vault_paths,
            file_contents=file_contents,
        )
