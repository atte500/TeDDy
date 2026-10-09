import logging
import os
from collections.abc import Callable, Sequence
from importlib import resources

import yaml

from teddy_executor.core.domain.models.drift_report import DriftReport
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

# Config files that must NEVER be overwritten once they exist, even when
# ``overwrite=True`` is passed. These files hold data the tool cannot
# regenerate (e.g. the user's LLM API key in ``.env``); the remaining config
# files are regenerable defaults that ``teddy init config`` intentionally resets.
_CREATE_ONLY_CONFIG_FILES = frozenset({".env"})

# Bundled Markdown templates copied into a project's ``docs/templates/`` by
# ``_init_templates``. Kept as a fixed manifest (rather than a directory
# listing) so the copy is deterministic and mirrors the ``_init_prompts``
# pattern. Single source of truth for the template names, also imported by the
# unit tests to avoid shadow literals.
_TEMPLATE_FILES = [
    "specification-document.md",
    "task-brief.md",
    "case-file.md",
    "vertical-slice.md",
    "milestone.md",
    "component-design.md",
    "ARCHITECTURE.md",
    "PROJECT.md",
    "makefile.md",
    "ci.md",
    "pre-commit.md",
]

# Bundled prompt XMLs copied into a project's ``.teddy/prompts/`` by
# ``_init_prompts`` and compared by ``check_drift``. Kept as a fixed manifest
# (mirroring ``_TEMPLATE_FILES``) so the copy routine and the drift check share
# one single source of truth.
_PROMPT_FILES = [
    "architect.xml",
    "assistant.xml",
    "debugger.xml",
    "developer.xml",
    "pathfinder.xml",
    "prototyper.xml",
]


class InitService(IInitUseCase):
    """
    Service for initializing projects.
    """

    def __init__(
        self,
        file_system: IFileSystemManager,
        config_dir: str | None = None,
        templates_dir: str | None = None,
    ):
        self._file_system = file_system
        # Find the config directory relative to the package root if not provided
        if config_dir:
            self._config_dir = config_dir
        else:
            # Use importlib.resources to find the bundled config templates
            resource_path = resources.files("teddy_executor.resources.config")
            # Ensure we resolve to an absolute string for compatibility with the FileSystem port
            self._config_dir = os.path.abspath(str(resource_path))
        # Templates ship as a sibling directory of the bundled config package. We
        # join onto ``resources`` (rather than resolving a ``resources.templates``
        # subpackage) so the directory needs no ``__init__.py``.
        if templates_dir:
            self._templates_dir = templates_dir
        else:
            resource_path = resources.files("teddy_executor.resources") / "templates"
            self._templates_dir = os.path.abspath(str(resource_path))

    def _read_bundled_resource(self, base_dir: str, filename: str) -> str | None:
        """Reads a bundled resource file from ``base_dir`` via the file-system port.

        Returns ``None`` when the resource is absent or unreadable, so callers
        can silently skip missing scaffold resources (logged at DEBUG).
        """
        try:
            target_path = os.path.join(base_dir, filename)
            if self._file_system.path_exists(target_path):
                return self._file_system.read_file(target_path)
        except (OSError, yaml.YAMLError, ImportError, AttributeError):
            logging.getLogger(__name__).debug(
                "Failed to load bundled resource %s", filename
            )
        return None

    @staticmethod
    def _format_init_status(count: int, overwrite: bool) -> str:
        """Formats the shared copy-result status string.

        Single-sources the "unchanged" / "updated (N files)" / "overwritten (N
        files)" vocabulary shared by the config, prompts, and templates copy
        routines.
        """
        if count == 0:
            return "unchanged"
        if overwrite:
            return f"overwritten ({count} files)"
        return f"updated ({count} files)"

    def _copy_bundled_files(
        self,
        dest_dir: str,
        filenames: Sequence[str],
        resolve_content: Callable[[str], str | None],
        overwrite: bool,
        create_only: frozenset[str] = frozenset(),
    ) -> str:
        """Copies bundled resources into ``dest_dir`` via the file-system port.

        Creates ``dest_dir`` when absent. Writes each ``filenames`` entry that is
        missing, or every entry when ``overwrite`` is set -- except names listed
        in ``create_only``, which are written only when absent. Content is
        supplied by ``resolve_content``; a ``None`` result silently skips a
        missing bundled resource. Returns the shared copy-result status string.
        """
        if not self._file_system.path_exists(dest_dir):
            self._file_system.create_directory(dest_dir)
        count = 0
        for fname in filenames:
            target_path = f"{dest_dir}/{fname}"
            exists = self._file_system.path_exists(target_path)
            if not exists or (overwrite and fname not in create_only):
                content = resolve_content(fname)
                if content is not None:
                    self._file_system.write_file(target_path, content)
                    count += 1
        return self._format_init_status(count, overwrite)

    def _get_default_content(self, filename: str) -> str | None:
        """Loads default content for a bundled config file.

        Embedded defaults (see ``_EMBEDDED_DEFAULTS``) take precedence; they are
        used for files that cannot ship as tracked dotfiles (e.g. the gitignored
        ``.env`` placeholder). Otherwise, content is loaded from the config
        directory using the file system port.
        """
        if filename in _EMBEDDED_DEFAULTS:
            return _EMBEDDED_DEFAULTS[filename]
        return self._read_bundled_resource(self._config_dir, filename)

    def _init_config_dir(self, overwrite: bool = False) -> str:
        """Copies config files (config.yaml, .gitignore, init.context, .env) to .teddy/.

        ``.env`` is create-only (see ``_CREATE_ONLY_CONFIG_FILES``): it is written
        only when absent and is NEVER overwritten once it exists, even when
        ``overwrite=True`` is passed, because it holds the user's non-regenerable
        LLM API key. The other three files are regenerable defaults and are
        overwritten as documented.

        Args:
            overwrite: If True, overwrite existing regenerable files with defaults.
                If False, only write missing files.

        Returns:
            A status string: "unchanged", "updated (N files)", or "overwritten (N files)".
        """
        return self._copy_bundled_files(
            dest_dir=".teddy",
            filenames=["config.yaml", ".gitignore", "init.context", ".env"],
            resolve_content=self._get_default_content,
            overwrite=overwrite,
            create_only=_CREATE_ONLY_CONFIG_FILES,
        )

    def _init_prompts(self, overwrite: bool = False) -> str:
        """Copies bundled prompt XMLs to .teddy/prompts/.

        Args:
            overwrite: If True, always overwrite existing files. If False, only write missing ones.

        Returns:
            A status string: "unchanged", "updated (N files)", or "overwritten (N files)".
        """
        return self._copy_bundled_files(
            dest_dir=".teddy/prompts",
            filenames=_PROMPT_FILES,
            resolve_content=lambda fname: self._get_default_content(f"prompts/{fname}"),
            overwrite=overwrite,
        )

    def _init_templates(self, overwrite: bool = False) -> str:
        """Copies bundled Markdown templates to docs/templates/.

        Args:
            overwrite: If True, always overwrite existing files.
                If False (default), only write missing files.

        Returns:
            A status string: "unchanged", "updated (N files)", or "overwritten (N files)".
        """
        return self._copy_bundled_files(
            dest_dir="docs/templates",
            filenames=_TEMPLATE_FILES,
            resolve_content=lambda fname: self._read_bundled_resource(
                self._templates_dir, fname
            ),
            overwrite=overwrite,
        )

    def ensure_initialized(self) -> str:
        """
        Ensures the .teddy directory and default files are present.

        Templates are intentionally NOT scaffolded here; ``docs/templates/`` is
        written only by the explicit ``teddy init templates`` subcommand
        (``ensure_templates_initialized``).

        Returns:
            A human-readable summary string (e.g., "Config: unchanged.
            Prompts: updated (6 files).").
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

        ``.env`` is create-only and is never overwritten once it exists, even
        when ``overwrite=True`` (see ``_init_config_dir``).

        Args:
            overwrite: If True, overwrite existing regenerable config files
                       (config.yaml, .gitignore, init.context) with defaults.
                       If False (default), only write missing files. ``.env`` is
                       written only when missing in either case.

        Returns:
            A human-readable status string (e.g., "Configuration files overwritten (3 files).").
        """
        status = self._init_config_dir(overwrite=overwrite)
        return f"Configuration files {status}."

    def ensure_templates_initialized(self, overwrite: bool = False) -> str:
        """
        Ensures Markdown templates are present in the docs/templates/ directory.

        Args:
            overwrite: If True, always overwrite existing template files with
                       defaults. If False (default), only write missing files.

        Returns:
            A human-readable status string (e.g., "Templates updated (11 files).").
        """
        status = self._init_templates(overwrite=overwrite)
        return f"Templates {status}."

    def _classify_drift(
        self,
        dest_dir: str,
        filenames: Sequence[str],
        resolve_bundled: Callable[[str], str | None],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Partitions ``filenames`` into (edited, missing) against bundled defaults.

        A file is MISSING when its user copy is absent. It is EDITED when the
        user copy exists, a bundled default is resolvable, and the two contents
        differ. Unresolvable bundled defaults are skipped (never reported as
        drift). Order is preserved from ``filenames`` for deterministic output.
        """
        edited: list[str] = []
        missing: list[str] = []
        for fname in filenames:
            user_path = f"{dest_dir}/{fname}"
            if not self._file_system.path_exists(user_path):
                missing.append(fname)
                continue
            bundled_content = resolve_bundled(fname)
            if bundled_content is None:
                continue
            if self._file_system.read_file(user_path) != bundled_content:
                edited.append(fname)
        return tuple(edited), tuple(missing)

    def check_drift(self) -> DriftReport:
        """Compares the user's prompts and templates against bundled defaults.

        Reports which ``.teddy/prompts/*.xml`` and ``docs/templates/*.md`` files
        have been EDITED away from their bundled default and which are MISSING,
        so the CLI preflight can advise ``teddy init prompts`` /
        ``teddy init templates``. An absent ``.teddy/prompts/`` directory simply
        makes every prompt report as MISSING (per-file check, no directory
        special-casing).
        """
        edited_prompts, missing_prompts = self._classify_drift(
            dest_dir=".teddy/prompts",
            filenames=_PROMPT_FILES,
            resolve_bundled=lambda fname: self._get_default_content(f"prompts/{fname}"),
        )
        edited_templates, missing_templates = self._classify_drift(
            dest_dir="docs/templates",
            filenames=_TEMPLATE_FILES,
            resolve_bundled=lambda fname: self._read_bundled_resource(
                self._templates_dir, fname
            ),
        )
        return DriftReport(
            edited_prompts=edited_prompts,
            missing_prompts=missing_prompts,
            edited_templates=edited_templates,
            missing_templates=missing_templates,
        )
