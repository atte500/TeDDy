from mistletoe import Document
from unittest.mock import MagicMock
from teddy_executor.core.services.action_parser_strategies import (
    parse_read_action,
    parse_prune_action,
)
from teddy_executor.core.services.parser_infrastructure import _PeekableStream
from teddy_executor.core.services.validation_rules.read import ReadActionValidator
from teddy_executor.core.services.validation_rules.prune import PruneActionValidator


def test_parse_read_action_with_file_path_alias():
    markdown = """
### `READ`
- **File Path:** [test.txt](/test.txt)
- **Description:** Read test.
"""
    doc = Document(markdown)
    md_list = doc.children[1]
    stream = _PeekableStream(iter([md_list]))

    action_data = parse_read_action(stream)

    assert action_data.params["resource"] == "test.txt"
    assert action_data.params["metadata_used_file_path_alias"] is True


def test_read_validator_enforces_strict_local_only():
    fs_mock = MagicMock()
    validator = ReadActionValidator(fs_mock)

    # Given a READ action with a URL and the File Path alias flag
    action = MagicMock()
    action.params = {
        "resource": "https://example.com",
        "metadata_used_file_path_alias": True,
    }
    action.node = None

    # When validated
    errors = validator.validate(action, context_paths={})

    # Then it should fail with the specific error
    assert len(errors) == 1
    assert "Strict Local Only" in errors[0].message


def test_read_validator_allows_url_for_resource_key():
    fs_mock = MagicMock()
    validator = ReadActionValidator(fs_mock)

    # Given a READ action with a URL using the 'Resource' key (no alias flag)
    action = MagicMock()
    action.params = {"resource": "https://example.com"}
    action.node = None

    # When validated
    errors = validator.validate(action, context_paths={})

    # Then it should pass (as URLs are allowed for Resource)
    assert len(errors) == 0


def test_parse_prune_action_with_file_path_alias():
    markdown = """
### `PRUNE`
- **File Path:** [test.txt](/test.txt)
- **Description:** Prune test.
"""
    doc = Document(markdown)
    md_list = doc.children[1]
    stream = _PeekableStream(iter([md_list]))

    action_data = parse_prune_action(stream)

    assert action_data.params["resource"] == "test.txt"
    assert action_data.params["metadata_used_file_path_alias"] is True


def test_prune_validator_enforces_strict_local_only():
    fs_mock = MagicMock()
    validator = PruneActionValidator(fs_mock)

    # Given a PRUNE action with a URL and the File Path alias flag
    action = MagicMock()
    action.params = {
        "resource": "https://example.com",
        "metadata_used_file_path_alias": True,
    }
    action.node = None

    # When validated
    errors = validator.validate(action, context_paths={})

    # Then it should fail with the specific error
    assert len(errors) == 1
    assert "Strict Local Only" in errors[0].message
