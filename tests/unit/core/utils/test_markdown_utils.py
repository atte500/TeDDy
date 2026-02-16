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
