"""
Regression test for Bug 06: Filepath parsing double underscore.

When a plan action (e.g., READ) contains a plain-text resource path with
double underscores (no Markdown link syntax), the path should be extracted
with underscores preserved. This test exercises the exact scenario from the bug
report: `**Resource:** src/teddy_executor/__main__.py` should yield
`src/teddy_executor/__main__.py`, not `src/teddy_executor/main.py`.
"""

from typing import Any

from teddy_executor.core.services.parser_metadata import parse_action_metadata


PLAIN_TEXT_PLAN = """# Test
- Status: Green

## Rationale
```text
Test
```

## Action Plan

### `READ`
- **Resource:** src/teddy_executor/__main__.py
- **Description:** Read the __main__.py file.
"""

INLINE_CODE_PLAN = """# Test
- Status: Green

## Rationale
```text
Test
```

## Action Plan

### `READ`
- **Resource:** `src/teddy_executor/__main__.py`
- **Description:** Read the file.
"""

LINK_FORMAT_PLAN = """# Test
- Status: Green

## Rationale
```text
Test
```

## Action Plan

### `READ`
- **Resource:** [src/teddy_executor/__main__.py](/src/teddy_executor/__main__.py)
- **Description:** Read the file.
"""


def _parse_resource_list(
    plan_text: str, link_key_map: dict | None = None
) -> dict[str, Any]:
    """Parse the metadata list from a plan and return params dict."""
    import mistletoe
    from mistletoe.block_token import List as MdList

    doc = mistletoe.block_token.Document(plan_text)

    def find_lists(node):
        lsts = []
        if isinstance(node, MdList):
            lsts.append(node)
        if hasattr(node, "children") and node.children:
            for child in node.children:
                lsts.extend(find_lists(child))
        return lsts

    lists = find_lists(doc)
    # The last list in the AST is the action metadata list
    if not lists:
        return {}
    metadata_list = lists[-1]
    link_key_map = link_key_map or {"Resource": "resource", "File Path": "path_alias"}
    _, params = parse_action_metadata(metadata_list, link_key_map=link_key_map)
    return params


def test_plain_text_resource_preserves_double_underscores():
    """
    Plain-text resource path with double underscores should be preserved.
    """
    params = _parse_resource_list(PLAIN_TEXT_PLAN)
    resource = params.get("resource", "")
    assert "__main__" in resource, (
        f"Expected double underscores in resource, got: {repr(resource)}"
    )
    assert resource == "src/teddy_executor/__main__.py", (
        f"Expected 'src/teddy_executor/__main__.py', got: {repr(resource)}"
    )


def test_inline_code_resource_preserves_double_underscores():
    """
    Inline code resource path with double underscores should be preserved.
    """
    params = _parse_resource_list(INLINE_CODE_PLAN)
    resource = params.get("resource", "")
    assert "__main__" in resource, (
        f"Expected double underscores in resource, got: {repr(resource)}"
    )
    assert resource == "src/teddy_executor/__main__.py", (
        f"Expected 'src/teddy_executor/__main__.py', got: {repr(resource)}"
    )


def test_link_format_resource_preserves_double_underscores():
    """
    Link-formatted resource path with double underscores should be preserved.
    (This already works, regression guard.)
    """
    params = _parse_resource_list(LINK_FORMAT_PLAN)
    resource = params.get("resource", "")
    assert "__main__" in resource, (
        f"Expected double underscores in resource, got: {repr(resource)}"
    )
    assert resource == "src/teddy_executor/__main__.py", (
        f"Expected 'src/teddy_executor/__main__.py', got: {repr(resource)}"
    )


def test_plain_text_path_alias_preserves_double_underscores():
    """
    'File Path' alias (used in CREATE actions) should also preserve underscores.
    """
    path_plan = PLAIN_TEXT_PLAN.replace("Resource:", "File Path:")
    params = _parse_resource_list(
        path_plan,
        link_key_map={"Resource": "resource", "File Path": "path_alias"},
    )
    # 'File Path' maps to 'path_alias' and then to 'resource' in parse_resource_action
    resource = params.get("path_alias", "")
    assert "__main__" in resource, (
        f"Expected double underscores in File Path, got: {repr(resource)}"
    )
    assert resource == "src/teddy_executor/__main__.py", (
        f"Expected 'src/teddy_executor/__main__.py', got: {repr(resource)}"
    )
