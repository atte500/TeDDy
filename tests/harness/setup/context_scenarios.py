"""Canonical context-payload scenarios for partition tests.

The context service decides a payload section from the scope key and the
own-session predicate, both of which a plain ``ProjectContext`` value can carry.
These scenarios supply the three paths that drive every branch, so a service
test reads one named bundle instead of inventing session directories.

The module is data only: it imports no context-service code, so it cannot couple
a test to the implementation it exercises.
"""

from collections.abc import Sequence
from typing import NamedTuple

SESSION_ROOT = ".teddy/sessions/20260101_120000-payload-layout"
SESSION_DOCUMENT = "docs/project/PROJECT.md"
OWN_HISTORY_REQUEST = f"{SESSION_ROOT}/initial_request.md"
TURN_DOCUMENT = "src/teddy_executor/core/services/context_service.py"


def content_for(path: str) -> str:
    """A deterministic body naming its path, so two paths never collide."""
    return f"CANONICAL CONTENT: {path}\n"


class ContextScenario(NamedTuple):
    """A scope mapping, the contents its paths resolve to, and the session root."""

    context_files: dict[str, list[str]]
    file_contents: dict[str, str]
    session_root: str | None

    def get_context_kwargs(self) -> dict[str, object]:
        """Forward the mapping with ``session_root`` to ``get_context``."""
        return {
            "context_files": self.context_files,
            "session_root": self.session_root,
        }


def context_scenario(
    session: Sequence[str] | None = None,
    turn: Sequence[str] | None = None,
    session_root: str | None = SESSION_ROOT,
) -> ContextScenario:
    """Build a scenario while always emitting both scope keys.

    An empty mapping reads as "no context files given" and falls back to the
    default vault paths, so the empty scenario keeps both keys present with
    empty lists to express an empty payload instead.
    """
    context_files = {"Session": list(session or []), "Turn": list(turn or [])}
    file_contents: dict[str, str] = {}
    for paths in context_files.values():
        for path in paths:
            file_contents.setdefault(path, content_for(path))
    return ContextScenario(
        context_files=context_files,
        file_contents=file_contents,
        session_root=session_root,
    )


MIXED_SCOPES = context_scenario(
    session=[SESSION_DOCUMENT, OWN_HISTORY_REQUEST],
    turn=[TURN_DOCUMENT],
)

EXPORT_SCOPES = context_scenario(
    session=[SESSION_DOCUMENT, OWN_HISTORY_REQUEST],
    turn=[TURN_DOCUMENT],
    session_root=None,
)
