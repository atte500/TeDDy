import textwrap
from mistletoe import Document
from teddy_executor.core.services.action_parser_complex import parse_edit_action
from teddy_executor.core.services.parser_infrastructure import _PeekableStream

VALID_ACTIONS = {
    "CREATE",
    "READ",
    "EDIT",
    "EXECUTE",
    "RESEARCH",
    "PROMPT",
    "PRUNE",
    "INVOKE",
    "RETURN",
}


def _parse_content(content: str):
    doc = Document(content)
    children = list(doc.children or [])
    stream = _PeekableStream(iter(children[1:]))
    return parse_edit_action(stream, VALID_ACTIONS)


def test_parse_edit_action_extracts_replace_all():
    """
    Asserts that parse_edit_action correctly identifies 'Replace All: true'.
    """
    content = textwrap.dedent("""\
        ### `EDIT`
        - **File Path:** [app.py](/app.py)
        - **Replace All:** true
        - **Description:** Bulk edit

        #### `FIND:`
        ```python
        old
        ```
        #### `REPLACE:`
        ```python
        new
        ```
        """)
    action_data = _parse_content(content)
    assert action_data.params.get("replace_all") is True


def test_parse_edit_action_defaults_replace_all_to_none_or_false():
    """
    Asserts that if Replace All is omitted, it's not present or is False.
    """
    content = textwrap.dedent("""\
        ### `EDIT`
        - **File Path:** [app.py](/app.py)
        - **Description:** Normal edit

        #### `FIND:`
        ```python
        old
        ```
        #### `REPLACE:`
        ```python
        new
        ```
        """)
    action_data = _parse_content(content)
    assert action_data.params.get("replace_all") in (None, False)
