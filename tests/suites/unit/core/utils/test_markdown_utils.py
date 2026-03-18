from teddy_executor.core.utils.markdown import get_fence_for_content


def test_get_fence_for_simple_content():
    """
    Given simple content with no backticks,
    When getting the fence,
    Then it should return the default triple backtick.
    """
    content = "hello world"
    assert get_fence_for_content(content) == "```"


def test_get_fence_for_content_with_triple_backticks():
    """
    Given content containing triple backticks,
    When getting the fence,
    Then it should return a quad backtick fence.
    """
    content = "Here is a code block:\n```python\nprint('hi')\n```"
    assert get_fence_for_content(content) == "````"


def test_get_fence_for_content_with_complex_backticks():
    """
    Given content containing varying lengths of backticks,
    When getting the fence,
    Then it should return a fence longer than the longest sequence.
    """
    content = "Contains `inline`, ```triple```, and ````quad```` backticks."
    assert get_fence_for_content(content) == "`````"


def test_get_language_from_path():
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
