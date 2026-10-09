"""Unit: the drift-check helper compares user prompts/templates against bundled defaults.

Seam Items 3/4 (session-behaviour): ``InitService.check_drift`` reports which
user prompt XMLs and template Markdown files have been EDITED away from their
bundled default and which are MISSING from the user's project, so the CLI
preflight can advise ``teddy init prompts`` / ``teddy init templates``.

The check enumerates the canonical default file set (``_PROMPT_FILES`` /
``_TEMPLATE_FILES``), so an absent user directory simply makes every file in
that set report as MISSING (see the slice's "No prompts directory" edge case).
"""

from tests.harness.setup.mocking import register_mock
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.services.init_service import InitService, _PROMPT_FILES


def _build_service(container):
    """Builds an InitService whose bundled roots are injected via the test seam."""
    fs = register_mock(container, IFileSystemManager)

    def _path_exists(path: str) -> bool:
        # A single template is deliberately absent from the user's workspace;
        # every bundled default and every other user file is present.
        return path != "docs/templates/ci.md"

    def _read_file(path: str) -> str:
        # The user edited exactly one prompt; every other file is byte-identical
        # to its bundled default (same basename -> same content).
        if path == ".teddy/prompts/pathfinder.xml":
            return "<user-edited pathfinder/>"
        return f"<{path.rsplit('/', 1)[-1]}>"

    fs.path_exists.side_effect = _path_exists
    fs.read_file.side_effect = _read_file

    return InitService(
        file_system=fs,
        config_dir="bundled/config",
        templates_dir="bundled/templates",
    )


def test_check_drift_reports_edited_prompt_and_missing_template(container):
    """Edited user prompts and missing user templates are surfaced distinctly."""
    service = _build_service(container)

    report = service.check_drift()

    assert report.edited_prompts == ("pathfinder.xml",)
    assert report.missing_prompts == ()
    assert report.edited_templates == ()
    assert report.missing_templates == ("ci.md",)


def test_check_drift_reports_every_prompt_missing_when_prompts_dir_absent(container):
    """An absent .teddy/prompts/ directory makes every manifest prompt MISSING.

    The check is per-file (there is no directory-existence shortcut), so a user
    who has never run init sees the full manifest reported as missing, while the
    independent docs/templates/ half stays clean.
    """
    fs = register_mock(container, IFileSystemManager)

    def _path_exists(path: str) -> bool:
        # The user's prompts directory is entirely absent; every bundled default
        # and every docs/templates/ default is present.
        return not path.startswith(".teddy/prompts/")

    def _read_file(path: str) -> str:
        return f"<{path.rsplit('/', 1)[-1]}>"

    fs.path_exists.side_effect = _path_exists
    fs.read_file.side_effect = _read_file

    service = InitService(
        file_system=fs,
        config_dir="bundled/config",
        templates_dir="bundled/templates",
    )

    report = service.check_drift()

    assert report.missing_prompts == tuple(_PROMPT_FILES)
    assert report.edited_prompts == ()
    assert report.missing_templates == ()
    assert report.edited_templates == ()
