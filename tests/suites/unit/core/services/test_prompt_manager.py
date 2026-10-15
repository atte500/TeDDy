import pytest
from pathlib import Path
from typing import Optional

from teddy_executor.core.services.prompt_manager import PromptManager

_MRP_SENTINEL = "<mrp>SHARED_PROTOCOL</mrp>"


def _write_mrp_root(tmp_path: Path, content: str = _MRP_SENTINEL) -> Path:
    """Creates a real, ``Traversable``-compatible resource root holding MRP.md.

    Injecting a real directory (instead of patching ``importlib.resources``)
    keeps the test hermetic and patch-free while fully controlling the MRP
    content the assembler appends.
    """
    root = tmp_path / "teddy_executor_resources"
    root.mkdir()
    (root / "MRP.md").write_text(content, encoding="utf-8")
    return root


def _arrange_teddy_prompt_resolution(mock_fs, *, agent_file: str, content: str) -> Path:
    """Wires ``mock_fs`` so a prompt resolves only from ``.teddy/prompts/``.

    Returns the standard three-level turn path used across these tests. The
    session root is empty, forcing resolution to fall through to the canonical
    ``.teddy/prompts/`` directory.
    """
    turn_path = Path(".teddy/sessions/my-session/01")
    session_root = turn_path.parent.as_posix()
    teddy_prompts_dir = (
        turn_path.parent.parent.parent.parent / ".teddy" / "prompts"
    ).as_posix()
    mock_fs.list_directory.side_effect = lambda d: {
        teddy_prompts_dir: [agent_file],
        session_root: [],
    }.get(d, [])
    mock_fs.path_exists.side_effect = lambda path: (
        path in [teddy_prompts_dir, f"{teddy_prompts_dir}/{agent_file}"]
    )
    mock_fs.read_file.side_effect = lambda p: {
        f"{teddy_prompts_dir}/{agent_file}": content,
    }.get(p, "")
    return turn_path


@pytest.fixture
def prompt_manager(mock_fs, mock_user_interactor):
    return PromptManager(
        file_system_manager=mock_fs, user_interactor=mock_user_interactor
    )


@pytest.fixture
def mrp_prompt_manager(tmp_path, mock_fs, mock_user_interactor):
    """A ``PromptManager`` whose MRP resource is a real, controlled ``tmp_path``.

    Using a real directory (instead of patching ``importlib.resources``) keeps
    these tests hermetic and patch-free while fully controlling the MRP content.
    """
    return PromptManager(
        file_system_manager=mock_fs,
        user_interactor=mock_user_interactor,
        mrp_resource_root=_write_mrp_root(tmp_path),
    )


def test_resolve_agent_metadata_returns_defaults_if_file_missing(
    prompt_manager, mock_fs
):
    # Arrange
    mock_fs.path_exists.return_value = False
    turn_path = Path("turns/01")

    # Act
    agent_name, meta, meta_path = prompt_manager.resolve_agent_metadata(turn_path)

    # Assert
    assert agent_name == "pathfinder"
    assert meta == {}
    assert meta_path == "turns/01/meta.yaml"


def test_fetch_system_prompt_resolves_from_teddy_prompts(mrp_prompt_manager, mock_fs):
    """
    Verifies that fetch_system_prompt resolves the agent XML from .teddy/prompts/
    when the session root does not have the prompt, and does NOT fall back to
    internal bundled resources. Uses extension-agnostic search.
    """
    turn_path = _arrange_teddy_prompt_resolution(
        mock_fs,
        agent_file="pathfinder.xml",
        content="<prompt>From .teddy/prompts/</prompt>",
    )

    # Act
    content = mrp_prompt_manager.fetch_system_prompt("pathfinder", turn_path)

    # Assert: the agent-specific content survives and the MRP block is appended
    assert "<prompt>From .teddy/prompts/</prompt>" in content
    assert _MRP_SENTINEL in content
    assert content.index("<prompt>From .teddy/prompts/</prompt>") < content.index(
        _MRP_SENTINEL
    )


def test_find_prompt_file_prefers_md_when_stem_has_both_extensions(
    prompt_manager, mock_fs
):
    """When a stem has both a ``.xml`` and a ``.md`` file, the ``.md`` file wins
    regardless of directory listing order."""
    # Arrange: the .xml is listed FIRST, so a naive first-match would return it.
    mock_fs.path_exists.return_value = True
    mock_fs.list_directory.return_value = ["pathfinder.xml", "pathfinder.md"]

    # Act
    result = prompt_manager._find_prompt_file(".teddy/prompts", "pathfinder")

    # Assert
    assert result == ".teddy/prompts/pathfinder.md"


def test_fetch_system_prompt_returns_persisted_composed_prompt_verbatim(
    mrp_prompt_manager, mock_fs
):
    """A composed session-root prompt is returned VERBATIM (no re-composition).

    Option A: the session-root file IS the composed system prompt, so the reader
    must return it unchanged -- no second ``Agent Name:`` header and no
    re-appended MRP block.
    """
    composed = (
        "Agent Name: Pathfinder\n\n"
        "<agent>AGENT_SPECIFIC</agent>\n\n"
        "<mrp>SHARED_PROTOCOL</mrp>"
    )
    turn_path = Path(".teddy/sessions/my-session/01")
    session_root = turn_path.parent.as_posix()
    session_prompt = f"{session_root}/pathfinder.xml"

    mock_fs.list_directory.side_effect = lambda d: {
        session_root: ["pathfinder.xml"],
    }.get(d, [])
    mock_fs.path_exists.side_effect = lambda path: (
        path
        in [
            session_root,
            session_prompt,
        ]
    )
    mock_fs.read_file.side_effect = lambda p: {session_prompt: composed}.get(p, "")

    # Act
    result = mrp_prompt_manager.fetch_system_prompt("pathfinder", turn_path)

    # Assert: returned exactly as persisted (single header, single MRP block)
    assert result == composed
    assert result.count("Agent Name:") == 1
    assert result.count("<mrp>") == 1


def test_get_available_agents_returns_prompt_files(prompt_manager, mock_fs):
    """
    Verifies that get_available_agents() lists all files from .teddy/prompts/
    and returns agent names as stems (regardless of extension).
    """
    # Arrange
    mock_fs.path_exists.return_value = True
    mock_fs.list_directory.return_value = [
        "architect.xml",
        "developer.md",
        "pathfinder.xml",
    ]

    # Act
    agents = prompt_manager.get_available_agents()

    # Assert: all files included, stems only
    assert agents == ["architect", "developer", "pathfinder"]
    mock_fs.path_exists.assert_called_once_with(".teddy/prompts/")
    mock_fs.list_directory.assert_called_once_with(".teddy/prompts/")


def test_get_available_agents_returns_empty_when_directory_missing(
    prompt_manager, mock_fs
):
    """
    Verifies that get_available_agents() returns an empty list when
    .teddy/prompts/ does not exist.
    """
    # Arrange
    mock_fs.path_exists.return_value = False

    # Act
    agents = prompt_manager.get_available_agents()

    # Assert
    assert agents == []
    mock_fs.path_exists.assert_called_once_with(".teddy/prompts/")


def test_get_available_agents_includes_all_files(prompt_manager, mock_fs):
    """
    Verifies that get_available_agents() returns all files, not just .xml.
    """
    # Arrange
    mock_fs.path_exists.return_value = True
    mock_fs.list_directory.return_value = [
        "architect.xml",
        "README.md",
        "debugger.xml",
        "notes.txt",
    ]

    # Act
    agents = prompt_manager.get_available_agents()

    # Assert: all files included
    assert agents == ["architect", "debugger", "notes", "README"]


def test_fetch_system_prompt_assembles_agent_content_and_mrp(
    mrp_prompt_manager, mock_fs
):
    """The assembled prompt is the agent-specific content, then a ``---``
    separator, then the shared MRP protocol content."""
    turn_path = _arrange_teddy_prompt_resolution(
        mock_fs,
        agent_file="pathfinder.xml",
        content="<agent>AGENT_SPECIFIC</agent>",
    )

    # Act
    result = mrp_prompt_manager.fetch_system_prompt("pathfinder", turn_path)

    # Assert
    assert (
        result == "<agent>AGENT_SPECIFIC</agent>\n\n---\n\n<mrp>SHARED_PROTOCOL</mrp>"
    )


def test_fetch_system_prompt_skips_mrp_when_response_format_present(
    mrp_prompt_manager, mock_fs
):
    """A resolved prompt that already carries ``<response_format>`` is a legacy
    override: it is returned UNCHANGED -- no MRP block and no ``---`` separator."""
    legacy_content = "<agent><response_format>INLINE</response_format></agent>"
    turn_path = _arrange_teddy_prompt_resolution(
        mock_fs,
        agent_file="pathfinder.xml",
        content=legacy_content,
    )

    result = mrp_prompt_manager.fetch_system_prompt("pathfinder", turn_path)

    assert result == legacy_content
    assert "<mrp>SHARED_PROTOCOL</mrp>" not in result


def test_fetch_system_prompt_raises_when_mrp_missing(
    tmp_path, mock_fs, mock_user_interactor
):
    """Missing ``MRP.md`` is a fatal protocol error: fail fast, never degrade
    silently."""
    empty_root = tmp_path / "teddy_executor_resources"
    empty_root.mkdir()  # no MRP.md written
    prompt_manager = PromptManager(
        file_system_manager=mock_fs,
        user_interactor=mock_user_interactor,
        mrp_resource_root=empty_root,
    )
    turn_path = _arrange_teddy_prompt_resolution(
        mock_fs,
        agent_file="pathfinder.xml",
        content="<agent/>",
    )

    with pytest.raises(FileNotFoundError, match="MRP"):
        prompt_manager.fetch_system_prompt("pathfinder", turn_path)


def test_fetch_system_prompt_appends_empty_mrp_without_error(
    tmp_path, mock_fs, mock_user_interactor
):
    """An existing but empty ``MRP.md`` is a degenerate-but-valid case: the
    assembly succeeds and appends an empty MRP block after the separator."""
    prompt_manager = PromptManager(
        file_system_manager=mock_fs,
        user_interactor=mock_user_interactor,
        mrp_resource_root=_write_mrp_root(tmp_path, content=""),
    )
    turn_path = _arrange_teddy_prompt_resolution(
        mock_fs,
        agent_file="pathfinder.xml",
        content="<agent/>",
    )

    result = prompt_manager.fetch_system_prompt("pathfinder", turn_path)

    assert result == "<agent/>\n\n---\n\n"


def test_fetch_system_prompt_returns_empty_when_agent_xml_missing(
    tmp_path, mock_fs, mock_user_interactor
):
    """No resolvable agent prompt returns an empty string (no header, no MRP),
    preserving the graceful-degradation contract and avoiding a spurious MRP
    load."""
    prompt_manager = PromptManager(
        file_system_manager=mock_fs,
        user_interactor=mock_user_interactor,
        mrp_resource_root=_write_mrp_root(tmp_path),
    )
    mock_fs.path_exists.return_value = False
    mock_fs.list_directory.return_value = []
    mock_fs.read_file.return_value = ""

    result = prompt_manager.fetch_system_prompt(
        "ghost", Path(".teddy/sessions/my-session/01")
    )

    assert result == ""


class _StubContentPromptManager(PromptManager):
    """Test double that injects the resolved prompt content directly.

    ``compose_system_prompt`` resolves its content through the public
    ``get_prompt_content`` seam, which delegates to
    ``prompts.find_prompt_content`` and therefore walks the REAL
    ``Path.cwd()`` -- it does NOT route through ``IFileSystemManager``.
    Overriding that one public seam keeps these tests hermetic without global
    patching and without a bare mock.
    """

    def __init__(self, content: Optional[str], **kwargs):
        super().__init__(**kwargs)
        self._stub_content = content

    def get_prompt_content(self, agent_name: str) -> Optional[str]:
        return self._stub_content


def _stub_manager(tmp_path, mock_fs, content: Optional[str]) -> PromptManager:
    """Builds a content-injecting manager backed by a real MRP resource root."""
    return _StubContentPromptManager(
        content=content,
        file_system_manager=mock_fs,
        mrp_resource_root=_write_mrp_root(tmp_path),
    )


def test_compose_system_prompt_assembles_agent_content_and_mrp(tmp_path, mock_fs):
    """``compose_system_prompt`` returns the agent-specific content, then a
    ``---`` separator, then the shared MRP protocol."""
    manager = _stub_manager(tmp_path, mock_fs, "<agent>AGENT_SPECIFIC</agent>")

    # Act
    result = manager.compose_system_prompt("pathfinder")

    # Assert
    assert (
        result == "<agent>AGENT_SPECIFIC</agent>\n\n---\n\n<mrp>SHARED_PROTOCOL</mrp>"
    )


@pytest.mark.parametrize("unresolved", [None, ""])
def test_compose_system_prompt_returns_none_when_content_unresolved(
    tmp_path, mock_fs, unresolved
):
    """No resolvable content yields ``None`` (the CLI's not-found signal),
    rather than a header-only or MRP-only fragment."""
    manager = _stub_manager(tmp_path, mock_fs, unresolved)

    # Act / Assert
    assert manager.compose_system_prompt("ghost") is None


def test_compose_system_prompt_skips_mrp_when_response_format_present(
    tmp_path, mock_fs
):
    """A legacy prompt that already carries ``<response_format>`` is returned
    UNCHANGED -- no MRP block and no ``---`` separator."""
    legacy = "<agent><response_format>INLINE</response_format></agent>"
    manager = _stub_manager(tmp_path, mock_fs, legacy)

    # Act
    result = manager.compose_system_prompt("pathfinder")

    # Assert
    assert result == legacy
    assert "<mrp>SHARED_PROTOCOL</mrp>" not in result
