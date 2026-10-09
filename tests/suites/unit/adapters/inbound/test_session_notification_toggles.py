"""Unit: the drift and update notifications honour their independent toggles.

Item 5 (session-behaviour): each user-facing preflight notification is gated by
its own checks.* config toggle (both default to enabled). A disabled toggle
suppresses ONLY the notification; the background version fetch still runs.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _display_drift_notification,
    _display_update_notification,
)
from teddy_executor.core.domain.models.drift_report import DriftReport
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService


def _write_fresh_update_cache(cache_path: Path) -> None:
    # Seeds a valid, in-TTL cache whose latest_version exceeds any real one, so
    # the update notification WOULD fire were it not for the toggle. This proves
    # the GATE rather than merely an absent cache.
    cache_path.write_text(
        json.dumps(
            {
                "latest_version": "999.0.0",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )


def test_drift_notification_suppressed_when_prompts_templates_toggle_disabled(
    env, capsys
):
    # A disabled checks.prompts_templates toggle must suppress the drift advice.
    config = env.mock_port(IConfigService)
    config.get_setting.side_effect = lambda key, default=None: (
        False if key == "checks.prompts_templates" else default
    )
    init = env.mock_port(IInitUseCase)
    init.check_drift.return_value = DriftReport(edited_prompts=("pathfinder.xml",))

    _display_drift_notification(env.container)

    captured = capsys.readouterr()
    assert "teddy init prompts" not in captured.out, (
        "A disabled checks.prompts_templates toggle must suppress the drift "
        f"advice; got: {captured.out!r}"
    )


def test_update_notification_suppressed_when_update_toggle_disabled(
    env, capsys, tmp_path
):
    # A disabled checks.update toggle must suppress the update notification.
    config = env.mock_port(IConfigService)
    config.get_setting.side_effect = lambda key, default=None: (
        False if key == "checks.update" else default
    )
    cache_path = tmp_path / ".update_cache.json"
    _write_fresh_update_cache(cache_path)

    _display_update_notification(env.container, cache_path)

    captured = capsys.readouterr()
    assert "new version" not in captured.out.lower(), (
        "A disabled checks.update toggle must suppress the update notification; "
        f"got: {captured.out!r}"
    )
