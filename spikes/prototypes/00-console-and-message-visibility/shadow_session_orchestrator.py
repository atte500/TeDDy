"""
Shadow SessionOrchestrator with console visibility helpers.

This file replicates the structure of the real SessionOrchestrator and adds
three helper functions that will be extracted into the production codebase.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, cast

import re

logger = logging.getLogger(__name__)


def extract_status_emoji(raw_status: str) -> str:
    """Extracts the status emoji, preferring anchored status lines.
    
    Mirrors the implementation in textual_plan_reviewer_helpers.py.
    """
    # Priority 1: Anchored status line
    anchored_match = re.search(
        r"^- \*\*Status:\*\*.*([🟢🟡🔴])", raw_status, re.MULTILINE
    )
    if anchored_match:
        return anchored_match.group(1)
    # Priority 2: Fallback to first occurring emoji
    emojis = re.findall(r"[🟢🟡🔴]", raw_status)
    return emojis[0] if emojis else ""


def _print_initial_request(message: Optional[str], is_session: bool) -> None:
    """Print the initial user request before the turn header.

    Only prints when is_session=True and message is non-empty.
    Output::
        Initial Request:
        {content}
    
    Follows by a blank line separator.
    """
    if not is_session or not message or not message.strip():
        return
    import typer

    typer.secho("Initial Request:")
    typer.secho(message.strip())
    typer.secho("")  # blank line separator


def _print_header_bar(plan: Any, is_session: bool) -> None:
    """Print the plan status emoji and title after telemetry, before actions.

    Only prints when is_session=True.
    Output: {emoji} {title}  (no blank lines around it)
    """
    if not is_session:
        return
    raw_status = plan.metadata.get("Status") or plan.metadata.get("status") or ""
    emoji = extract_status_emoji(raw_status)
    title = plan.title or ""
    parts = [p for p in [emoji, title] if p]
    if parts:
        import typer
        typer.secho(" ".join(parts))


def _print_user_message(message: Optional[str], is_session: bool) -> None:
    """Print the user message after all actions execute.

    Only prints when is_session=True and message is non-empty.
    Output::
        (blank line)
        User Message:
        {content}
        (trailing newline)
    """
    if not is_session or not message or not message.strip():
        return
    import typer

    typer.secho("")  # blank line before User Message
    typer.secho("User Message:")
    typer.secho(message.strip())
    typer.secho("")  # trailing newline