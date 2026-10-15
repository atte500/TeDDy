"""Shared session-termination and interrupt notice strings.

Single source for the resume hint and the interrupt-notice composition so the
session-loop boundary (interrupt notices) and the session orchestrator
(termination notices) render the same actionable next step.

The interrupt notice names the key the user actually pressed: the shared
guard's ``source`` marker (set by the bare-``q`` listener callback) when
present, and the ``Ctrl+C`` default otherwise.
"""

from typing import Optional

from teddy_executor.core.utils.interrupt_guard import INTERRUPT_REASON

# The single resume hint shared by every termination and interrupt notice.
RESUME_HINT = "To continue the session, use `teddy resume`."

# Key label used when no interrupt source was recorded (a genuine Ctrl+C).
DEFAULT_INTERRUPT_KEY = "Ctrl+C"


def format_interrupt_notice(source: Optional[str] = None) -> str:
    """Compose the one-line interrupt notice naming the pressed key.

    The prefix is derived from ``INTERRUPT_REASON`` (sans its trailing period)
    so the boundary notice and the audit-trail reason stay in lockstep; the key
    label defaults to ``Ctrl+C`` when no source was recorded.
    """
    key = source or DEFAULT_INTERRUPT_KEY
    return f"{INTERRUPT_REASON.removesuffix('.')} ({key}). {RESUME_HINT}"
