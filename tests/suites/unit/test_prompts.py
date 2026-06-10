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