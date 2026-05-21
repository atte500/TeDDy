from teddy_executor.core.utils.markdown import get_fence_for_content


def test_get_fence_for_simple_content(container):
    """
    Given simple content with no backticks,
    When getting the fence,
    Then it should return the default triple backtick.
    """
    content = "hello world"
    assert get_fence_for_content(content) == "```"


def test_get_fence_for_content_with_triple_backticks(container):
    """
    Given content containing triple backticks,
    When getting the fence,
    Then it should return a quad backtick fence.
    """
    content = "Here is a code block:\n```python\nprint('hi')\n```"
    assert get_fence_for_content(content) == "````"


def test_get_fence_for_content_with_complex_backticks(container):
    """
    Given content containing varying lengths of backticks,
    When getting the fence,
    Then it should return a fence longer than the longest sequence.
    """
    content = "Contains `inline`, ```triple```, and ````quad```` backticks."
    assert get_fence_for_content(content) == "`````"


def test_get_language_from_path(container):
    from teddy_executor.core.utils.markdown import get_language_from_path

    # Common extensions mapping
    assert get_language_from_path("src/main.py") == "python"
    assert get_language_from_path("README.md") == "markdown"
    assert get_language_from_path("script.sh") == "shell"
    assert get_language_from_path("style.css") == "css"
    assert get_language_from_path("index.html") == "html"
    assert get_language_from_path("app.js") == "javascript"
    assert get_language_from_path("app.ts") == "typescript"
    assert get_language_from_path("data.json") == "json"
    assert get_language_from_path("config.yaml") == "yaml"
    assert get_language_from_path("config.yml") == "yaml"
    assert get_language_from_path("script.bash") == "shell"
    assert get_language_from_path("script.ps1") == "powershell"
    assert get_language_from_path("Program.cs") == "csharp"
    assert get_language_from_path("main.tf") == "terraform"
    assert get_language_from_path("header.h") == "c"
    assert get_language_from_path("main.cpp") == "cpp"
    assert get_language_from_path("script.rb") == "ruby"

    # Configs map to ini
    assert get_language_from_path("config.cfg") == "ini"
    assert get_language_from_path("config.ini") == "ini"

    # Fallback to extension
    assert get_language_from_path("data.csv") == "csv"
    assert get_language_from_path("index.php") == "php"
    assert get_language_from_path("main.go") == "go"

    # No extension
    assert get_language_from_path("Makefile") == "text"
    assert get_language_from_path("LICENSE") == "text"


def test_session_history_helpers(container):
    from teddy_executor.core.utils.markdown import (
        is_session_file_path,
        is_session_history_path,
        get_session_history_display_name,
        get_session_history_sort_key,
    )

    # 1. Test is_session_file_path
    assert is_session_file_path(".teddy/sessions/XYZ/initial_request.md") is True
    assert is_session_file_path("src/main.py") is False

    # 2. Test is_session_history_path
    assert is_session_history_path(".teddy/sessions/XYZ/initial_request.md") is True
    assert is_session_history_path(".teddy/sessions/XYZ/01/plan.md") is True
    assert is_session_history_path(".teddy/sessions/XYZ/01/report.md") is True
    assert is_session_history_path(".teddy/sessions/XYZ/01/meta.yaml") is False
    assert is_session_history_path("src/main.py") is False

    # 3. Test get_session_history_display_name
    assert (
        get_session_history_display_name(".teddy/sessions/XYZ/initial_request.md")
        == "Initial Request"
    )
    assert (
        get_session_history_display_name(".teddy/sessions/XYZ/01/plan.md")
        == "Turn 1: Plan"
    )
    assert (
        get_session_history_display_name(".teddy/sessions/XYZ/01/report.md")
        == "Turn 1: Execution Report"
    )
    assert get_session_history_display_name(".teddy/sessions/XYZ/01/meta.yaml") is None
    assert get_session_history_display_name("src/main.py") is None

    # 4. Test get_session_history_sort_key
    assert get_session_history_sort_key(".teddy/sessions/XYZ/initial_request.md") == (
        0,
        0,
    )
    assert get_session_history_sort_key(".teddy/sessions/XYZ/01/plan.md") == (1, 1)
    assert get_session_history_sort_key(".teddy/sessions/XYZ/01/report.md") == (1, 2)
    assert get_session_history_sort_key("src/main.py") == (999999, 999999)
