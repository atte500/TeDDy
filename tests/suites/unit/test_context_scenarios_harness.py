"""Contract tests for the canonical context-payload scenarios.

The scenarios exist so a context-service test can drive the session-resources
partition without real session directories. These tests pin the shape the
scenarios promise: both scope keys always present, declaration order preserved,
one deterministic content string per path, and exactly one partition branch per
canonical path.
"""

from teddy_executor.core.utils.markdown import is_own_session_path
from tests.harness.setup.context_scenarios import (
    MIXED_SCOPES,
    OWN_HISTORY_REQUEST,
    SESSION_DOCUMENT,
    SESSION_ROOT,
    TURN_DOCUMENT,
    content_for,
    context_scenario,
)


def test_mixed_scopes_pairs_a_session_document_own_history_and_a_turn_path():
    """The canonical bundle carries exactly the three paths the partition needs."""
    scenario = MIXED_SCOPES

    assert scenario.session_root == SESSION_ROOT
    assert scenario.context_files == {
        "Session": [SESSION_DOCUMENT, OWN_HISTORY_REQUEST],
        "Turn": [TURN_DOCUMENT],
    }
    assert set(scenario.file_contents) == {
        SESSION_DOCUMENT,
        OWN_HISTORY_REQUEST,
        TURN_DOCUMENT,
    }


def test_both_scope_keys_survive_an_empty_scenario():
    """An empty mapping reads as "no context files given", so the builder keeps
    both keys to express an empty payload instead of the default vault."""
    scenario = context_scenario()

    assert scenario.context_files == {"Session": [], "Turn": []}
    assert scenario.file_contents == {}


def test_scope_lists_preserve_declaration_order():
    """Session order is the user's knob, so the builder must not sort."""
    scenario = context_scenario(session=["b.md", "a.md"], turn=["c.py"])

    assert scenario.context_files["Session"] == ["b.md", "a.md"]
    assert scenario.context_files["Turn"] == ["c.py"]


def test_content_is_deterministic_and_unique_per_path():
    assert content_for(SESSION_DOCUMENT) == content_for(SESSION_DOCUMENT)
    assert content_for(SESSION_DOCUMENT) != content_for(TURN_DOCUMENT)
    assert content_for(TURN_DOCUMENT) == MIXED_SCOPES.file_contents[TURN_DOCUMENT]


def test_a_path_in_both_scopes_carries_one_content_entry():
    scenario = context_scenario(session=[TURN_DOCUMENT], turn=[TURN_DOCUMENT])

    assert scenario.context_files["Session"] == [TURN_DOCUMENT]
    assert scenario.context_files["Turn"] == [TURN_DOCUMENT]
    assert scenario.file_contents == {TURN_DOCUMENT: content_for(TURN_DOCUMENT)}


def test_get_context_kwargs_forwards_the_scope_mapping_and_the_root():
    scenario = MIXED_SCOPES

    assert scenario.get_context_kwargs() == {
        "context_files": scenario.context_files,
        "session_root": SESSION_ROOT,
    }


def test_each_canonical_path_drives_exactly_one_partition_branch():
    """Guards the fixture: if a path changed branch, the scenario would silently
    stop exercising the case it is named for."""
    assert is_own_session_path(SESSION_DOCUMENT, SESSION_ROOT) is False
    assert is_own_session_path(OWN_HISTORY_REQUEST, SESSION_ROOT) is True
    assert is_own_session_path(TURN_DOCUMENT, SESSION_ROOT) is False
