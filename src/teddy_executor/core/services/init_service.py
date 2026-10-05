import logging
import os
from importlib import resources

import yaml

from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager

# Embedded defaults for the fixed ``.teddy`` scaffolding that cannot ship as
# tracked source files. The bundled ``resources/config/`` directory cannot hold
# a live ``.gitignore`` (its ``*`` rule would be a real ignore rule for the
# source tree, blocking any sibling dotfile), so both files are kept as string
# constants. This sidesteps the git-tracking hazard entirely and makes the
# scaffold unit-testable.
_ENV_PLACEHOLDER = (
    "# TeDDy secrets. This gitignored file holds your provider credentials.\n"
    "# The bundled config.yaml reads the LLM key from this file's env var.\n"
    "# Paste your OpenRouter (or other provider) key below.\n"
    "TEDDY_LLM_API_KEY=\n"  # pragma: allowlist secret
)

_GITIGNORE_PLACEHOLDER = "# Ignore everything in the .teddy directory by default\n*\n"

_EMBEDDED_DEFAULTS = {
    ".env": _ENV_PLACEHOLDER,
    ".gitignore": _GITIGNORE_PLACEHOLDER,
}


class InitService(IInitUseCase):
    """
    Service for initializing projects.
    """

    def __init__(self, file_system: IFileSystemManager, config_dir: str | None = None):
        self._file_system = file_system
        # Find the config directory relative to the package root if not provided
        if config_dir:
            self._config_dir = config_dir
        else:
            # Use importlib.resources to find the bundled config templates
            resource_path = resources.files("teddy_executor.resources.config")
            # Ensure we resolve to an absolute string for compatibility with the FileSystem port
            self._config_dir = os.path.abspath(str(resource_path))

    def _get_default_content(self, filename: str) -> str | None:
        """Loads default content for a bundled config file.

        Embedded defaults (see ``_EMBEDDED_DEFAULTS``) take precedence; they are
        used for files that cannot ship as tracked dotfiles (e.g. the gitignored
        ``.env`` placeholder). Otherwise, content is loaded from the config
        directory using the file system port.
        """
        if filename in _EMBEDDED_DEFAULTS:
            return _EMBEDDED_DEFAULTS[filename]
        try:
            target_path = os.path.join(self._config_dir, filename)
            if self._file_system.path_exists(target_path):
                return self._file_system.read_file(target_path)
        except (OSError, yaml.YAMLError, ImportError, AttributeError):
            logging.getLogger(__name__).debug(
                "Failed to load default content for %s", filename
            )
        return None

    def _init_config_dir(self, overwrite: bool = False) -> str:
        """Copies config files (config.yaml, .gitignore, init.context, .env) to .teddy/.

        Args:
            overwrite: If True, always overwrite existing files. If False, only write missing ones.

        Returns:
            A status string: "unchanged", "updated (N files)", or "overwritten (N files)".
        """
        config_files = ["config.yaml", ".gitignore", "init.context", ".env"]
        count = 0
        for fname in config_files:
            target_path = f".teddy/{fname}"
            if overwrite or not self._file_system.path_exists(target_path):
                content = self._get_default_content(fname)
                if content is not None:
                    self._file_system.write_file(target_path, content)
                    count += 1
        if count == 0:
            return "unchanged"
        if overwrite:
            return f"overwritten ({count} files)"
        return f"updated ({count} files)"

    def _init_prompts(self, overwrite: bool = False) -> str:
        """Copies bundled prompt XMLs to .teddy/prompts/.

        Args:
            overwrite: If True, always overwrite existing files. If False, only write missing ones.

        Returns:
            A status string: "unchanged", "updated (N files)", or "overwritten (N files)".
        """
        prompts_dir = ".teddy/prompts"
        if not self._file_system.path_exists(prompts_dir):
            self._file_system.create_directory(prompts_dir)

        prompt_files = [
            "architect.xml",
            "assistant.xml",
            "debugger.xml",
            "developer.xml",
            "pathfinder.xml",
            "prototyper.xml",
        ]
        count = 0
        for fname in prompt_files:
            target_path = f"{prompts_dir}/{fname}"
            if overwrite or not self._file_system.path_exists(target_path):
                content = self._get_default_content(f"prompts/{fname}")
                if content is not None:
                    self._file_system.write_file(target_path, content)
                    count += 1
        if count == 0:
            return "unchanged"
        if overwrite:
            return f"overwritten ({count} files)"
        return f"updated ({count} files)"

    def ensure_initialized(self) -> str:
        """
        Ensures the .teddy directory and default files are present.

        Returns:
            A human-readable summary string (e.g., "Config: unchanged. Prompts: updated (3 files).").
        """
        if not self._file_system.path_exists(".teddy"):
            self._file_system.create_directory(".teddy")

        config_status = self._init_config_dir(overwrite=False)
        prompts_status = self._init_prompts(overwrite=False)
        return f"Config: {config_status}. Prompts: {prompts_status}."

    def ensure_prompts_initialized(self, overwrite: bool = True) -> str:
        """
        Ensures prompt XML files are present in the .teddy/prompts/ directory.

        Args:
            overwrite: If True, always overwrite existing prompt files with defaults.
                       If False (default), only write missing files.

        Returns:
            A human-readable status string (e.g., "Prompts overwritten (6 files).").
        """
        status = self._init_prompts(overwrite=overwrite)
        return f"Prompts {status}."

    def ensure_config_initialized(self, overwrite: bool = True) -> str:
        """
        Ensures configuration files (config.yaml, .gitignore, init.context, .env) are present in the .teddy/ directory.

        Args:
            overwrite: If True, always overwrite existing config files with defaults.
                       If False (default), only write missing files.

        Returns:
            A human-readable status string (e.g., "Configuration files overwritten (4 files).").
        """
        status = self._init_config_dir(overwrite=overwrite)
        return f"Configuration files {status}."
