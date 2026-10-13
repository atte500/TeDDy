"""Unit tests for the ``_resolve_agent`` decision table (pipeline default agent).

This file pins the pure resolution matrix of the single-sourced
``_resolve_agent`` helper: an explicit ``--agent`` / ``-a`` value always wins;
when the flag is unset, pipeline runs resolve to the action-first ``assistant``
agent and every other run to ``pathfinder``.
"""

import pytest

from teddy_executor.__main__ import _resolve_agent


@pytest.mark.parametrize(
    ("agent", "pipeline", "expected"),
    [
        (None, False, "pathfinder"),  # unset flag, no pipeline -> pathfinder
        (None, True, "assistant"),  # unset flag, pipeline -> assistant
        ("architect", False, "architect"),  # explicit flag wins (no pipeline)
        ("architect", True, "architect"),  # explicit flag wins over pipeline default
    ],
)
def test_resolve_agent_resolution_matrix(agent, pipeline, expected):
    """An explicit flag wins; otherwise the pipeline-aware default is used."""
    assert _resolve_agent(agent, pipeline) == expected


def test_resolve_agent_explicit_pathfinder_wins_in_pipeline_mode():
    """An explicit ``-a pathfinder`` must NOT be overridden by the pipeline default."""
    assert _resolve_agent("pathfinder", True) == "pathfinder"
