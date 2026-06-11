from pathlib import Path
from teddy_executor import prompts


def test_find_prompt_content_does_not_fallback_to_bundled(fs):
    """
    Verifies that find_prompt_content does NOT fall back to bundled resources
    when the prompt is not present in .teddy/prompts/.
    """
    # Arrange: create the bundled resource directory in pyfakefs to simulate fallback
    bundled_dir = Path(prompts.__file__).parent / "resources" / "config" / "prompts"
    bundled_dir.mkdir(parents=True, exist_ok=True)
    (bundled_dir / "pathfinder.xml").write_text("<bundled>prompt</bundled>")

    # Create .teddy/prompts/ but WITHOUT pathfinder.xml
    Path(".teddy/prompts").mkdir(parents=True, exist_ok=True)

    # Act
    result = prompts.find_prompt_content("pathfinder")

    # Assert
    # Before fix: returns "<bundled>prompt</bundled>" (fails)
    # After fix: returns None (passes)
    assert result is None, "Should not fall back to bundled resources"


# ---------------------------------------------------------------------------
# list_prompt_names utility for get-prompt error enrichment
# ---------------------------------------------------------------------------


def test_list_prompt_names_returns_xml_files(fs):
    """
    Verifies that list_prompt_names() returns .xml file stems from .teddy/prompts/
    when the directory exists in the CWD hierarchy.
    """
    # Arrange
    Path(".teddy/prompts").mkdir(parents=True, exist_ok=True)
    (Path(".teddy/prompts") / "architect.xml").write_text("<prompt>")
    (Path(".teddy/prompts") / "developer.xml").write_text("<prompt>")
    (Path(".teddy/prompts") / "pathfinder.xml").write_text("<prompt>")

    # Act
    result = prompts.list_prompt_names()

    # Assert
    assert result == ["architect", "developer", "pathfinder"]


def test_list_prompt_names_returns_empty_when_directory_missing(fs):
    """
    Verifies that list_prompt_names() returns empty list when
    no .teddy/prompts/ directory exists in the CWD hierarchy.
    """
    # Arrange: no .teddy/prompts/ directory

    # Act
    result = prompts.list_prompt_names()

    # Assert
    assert result == []


def test_list_prompt_names_returns_empty_when_directory_empty(fs):
    """
    Verifies that list_prompt_names() returns empty list when
    .teddy/prompts/ exists but is empty.
    """
    # Arrange
    Path(".teddy/prompts").mkdir(parents=True, exist_ok=True)

    # Act
    result = prompts.list_prompt_names()

    # Assert
    assert result == []


def test_list_prompt_names_filters_non_xml_files(fs):
    """
    Verifies that list_prompt_names() filters out non-xml files.
    """
    # Arrange
    Path(".teddy/prompts").mkdir(parents=True, exist_ok=True)
    (Path(".teddy/prompts") / "architect.xml").write_text("<prompt>")
    (Path(".teddy/prompts") / "README.md").write_text("# Readme")
    (Path(".teddy/prompts") / "debugger.xml").write_text("<prompt>")
    (Path(".teddy/prompts") / "notes.txt").write_text("notes")

    # Act
    result = prompts.list_prompt_names()

    # Assert
    assert result == ["architect", "debugger"]
