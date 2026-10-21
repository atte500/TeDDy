"""Seam invariants: the session handlers accept no ``api_key`` parameter.

The command-line override is gone, so the parameter chain it fed must go too.
The interactive prompt and ``TEDDY_LLM_API_KEY`` remain the only key paths, and
these checks stop a future edit from silently reintroducing the plumbing.
"""

import inspect

import pytest

from teddy_executor.adapters.inbound import session_cli_handlers as handlers


@pytest.mark.parametrize(
    "seam",
    [
        handlers.handle_new_session,
        handlers.handle_resume_session,
        handlers._sync_and_display_session_meta,
    ],
    ids=["new_session", "resume_session", "sync_session_meta"],
)
def test_session_handler_seam_declares_no_api_key(seam):
    """Each session handler seam exposes no ``api_key`` parameter."""
    assert "api_key" not in inspect.signature(seam).parameters
