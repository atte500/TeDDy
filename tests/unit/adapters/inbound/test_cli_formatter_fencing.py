from teddy_executor.core.domain.models import ContextResult
from teddy_executor.adapters.inbound.cli_formatter import format_project_context


def test_format_project_context_uses_smart_fencing():
    """
    Given a ContextResult with file content containing triple backticks,
    When format_project_context is called,
    Then the output should use a fence of at least 4 backticks for that file.
    """
    # GIVEN
    file_content_with_backticks = "Here is a code block:\n```python\nprint('hi')\n```"

    context = ContextResult(
        system_info={"os": "Linux"},
        repo_tree=".",
        context_vault_paths=["README.md"],
        file_contents={"README.md": file_content_with_backticks},
    )

    # WHEN
    result = format_project_context(context)

    # THEN
    # We look for the file header
    assert "--- README.md ---" in result
    # And we expect a smart fence (quad backticks)
    assert "````markdown" in result or "````" in result
    assert file_content_with_backticks in result

    # Specifically ensure we don't have triple backticks as the fence
    # (since the content has triple backticks, using triple backticks as fence would be ambiguous/wrong)
    # Ideally, we check for exact structural match.
    # Note: cli_formatter adds extension. README.md -> .md -> markdown
    expected_segment_with_lang = (
        "````markdown\nHere is a code block:\n```python\nprint('hi')\n```\n````"
    )

    assert expected_segment_with_lang in result


def test_format_project_context_uses_smart_fencing_deep():
    """
    Given a ContextResult with file content containing QUAD backticks,
    When format_project_context is called,
    Then the output should use a fence of at least 5 backticks.
    """
    # GIVEN
    file_content = "Deep nesting:\n````\ncode\n````"

    context = ContextResult(
        system_info={},
        repo_tree=".",
        context_vault_paths=["deep.txt"],
        file_contents={"deep.txt": file_content},
    )

    # WHEN
    result = format_project_context(context)

    # THEN
    # We expect 5 backticks
    assert "`````" in result
    assert file_content in result
