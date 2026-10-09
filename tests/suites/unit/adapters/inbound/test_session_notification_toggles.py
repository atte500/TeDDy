"""Unit: the drift and update notifications honour their independent toggles.

Item 5 (session-behaviour): each user-facing preflight notification is gated by
its own checks.* config toggle (defaulting to enabled). The drift notification is
split PER CHANNEL -- ``checks.prompts`` and ``checks.templates`` gate the prompts
and templates advice independently -- and the helper returns the list of checks
that actually fired so the shared disable-footer can name them. A disabled toggle
suppresses ONLY its notification; the background version fetch still runs.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _display_checks_footer,
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


def test_drift_notification_suppressed_when_prompts_toggle_disabled(env, capsys):
    # A disabled checks.prompts toggle must suppress the PROMPTS drift advice and
    # exclude the prompts check from the returned fired-keys.
    config = env.mock_port(IConfigService)
    config.get_setting.side_effect = lambda key, default=None: (
        False if key == "checks.prompts" else default
    )
    init = env.mock_port(IInitUseCase)
    init.check_drift.return_value = DriftReport(edited_prompts=("pathfinder.xml",))

    fired = _display_drift_notification(env.container)

    captured = capsys.readouterr()
    assert "teddy init prompts" not in captured.out, (
        "A disabled checks.prompts toggle must suppress the prompts drift "
        f"advice; got: {captured.out!r}"
    )
    assert fired == [], (
        "A disabled checks.prompts toggle must not report a fired check; "
        f"got: {fired!r}"
    )


def test_drift_notification_suppressed_when_templates_toggle_disabled(env, capsys):
    # A disabled checks.templates toggle must suppress the TEMPLATES drift advice
    # independently of checks.prompts.
    config = env.mock_port(IConfigService)
    config.get_setting.side_effect = lambda key, default=None: (
        False if key == "checks.templates" else default
    )
    init = env.mock_port(IInitUseCase)
    init.check_drift.return_value = DriftReport(edited_templates=("vertical-slice.md",))

    fired = _display_drift_notification(env.container)

    captured = capsys.readouterr()
    assert "teddy init templates" not in captured.out, (
        "A disabled checks.templates toggle must suppress the templates drift "
        f"advice; got: {captured.out!r}"
    )
    assert fired == [], (
        "A disabled checks.templates toggle must not report a fired check; "
        f"got: {fired!r}"
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

    fired = _display_update_notification(env.container, cache_path)

    captured = capsys.readouterr()
    assert "new version" not in captured.out.lower(), (
        "A disabled checks.update toggle must suppress the update notification; "
        f"got: {captured.out!r}"
    )
    assert fired == [], (
        f"A disabled checks.update toggle must not report a fired check; got: {fired!r}"
    )


def test_drift_notification_fires_when_toggles_absent(env, capsys):
    # ABSENT checks.prompts / checks.templates keys (config lacks them) must default
    # to ENABLED, so the prompts advice still fires and its fired key is reported.
    # This locks the production default argument: mutating it to False would break
    # this characterization.
    config = env.mock_port(IConfigService)
    config.get_setting.side_effect = lambda key, default=None: default
    init = env.mock_port(IInitUseCase)
    init.check_drift.return_value = DriftReport(edited_prompts=("pathfinder.xml",))

    fired = _display_drift_notification(env.container)

    captured = capsys.readouterr()
    assert "teddy init prompts" in captured.out, (
        "An absent checks.prompts toggle must default to enabled so the drift "
        f"advice fires; got: {captured.out!r}"
    )
    assert fired == ["checks.prompts"], (
        "An enabled prompts check that fired must report 'checks.prompts'; "
        f"got: {fired!r}"
    )


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        (
            DriftReport(edited_prompts=("pathfinder.xml", "architect.xml")),
            "2 prompts in .teddy/prompts/ differ from this version's defaults",
        ),
        (
            DriftReport(missing_prompts=("pathfinder.xml",)),
            "1 prompt in .teddy/prompts/ is missing",
        ),
        (
            DriftReport(
                edited_prompts=("pathfinder.xml",),
                missing_prompts=("architect.xml", "developer.xml"),
            ),
            "3 prompts in .teddy/prompts/ differ from this version's defaults "
            "(1 changed, 2 missing)",
        ),
    ],
)
def test_drift_notification_count_aware_wording(env, capsys, report, expected):
    # The per-channel line distinguishes CHANGED from MISSING and is count-aware.
    config = env.mock_port(IConfigService)
    config.get_setting.side_effect = lambda key, default=None: default
    init = env.mock_port(IInitUseCase)
    init.check_drift.return_value = report

    _display_drift_notification(env.container)

    captured = capsys.readouterr()
    assert expected in captured.out, (
        f"Count-aware wording mismatch; expected {expected!r}; got: {captured.out!r}"
    )


def test_drift_notification_reports_both_channel_keys(env, capsys):
    # Both channels drifted and enabled -> both fired keys reported, prompts first.
    config = env.mock_port(IConfigService)
    config.get_setting.side_effect = lambda key, default=None: default
    init = env.mock_port(IInitUseCase)
    init.check_drift.return_value = DriftReport(
        edited_prompts=("pathfinder.xml",),
        missing_templates=("vertical-slice.md",),
    )

    fired = _display_drift_notification(env.container)

    captured = capsys.readouterr()
    assert fired == ["checks.prompts", "checks.templates"], (
        "Both drifted channels must report their keys in canonical order; "
        f"got: {fired!r}"
    )
    assert captured.out.index("teddy init prompts") < captured.out.index(
        "teddy init templates"
    ), f"Prompts line must precede the templates line; got: {captured.out!r}"


def test_update_notification_fires_when_update_toggle_absent(env, capsys, tmp_path):
    # An ABSENT checks.update toggle (config lacks the key) must default to ENABLED,
    # so the update notification still fires.
    config = env.mock_port(IConfigService)
    config.get_setting.side_effect = lambda key, default=None: default
    cache_path = tmp_path / ".update_cache.json"
    _write_fresh_update_cache(cache_path)

    _display_update_notification(env.container, cache_path)

    captured = capsys.readouterr()
    assert "new version" in captured.out.lower(), (
        "An absent checks.update toggle must default to enabled so the update "
        f"notification fires; got: {captured.out!r}"
    )


def test_update_notification_reports_fired_key_when_it_fires(env, capsys, tmp_path):
    # When the update notification actually fires (toggle enabled AND a newer
    # version is displayed), the helper must report its fired key so the shared
    # disable-footer can name it.
    config = env.mock_port(IConfigService)
    config.get_setting.side_effect = lambda key, default=None: default
    cache_path = tmp_path / ".update_cache.json"
    _write_fresh_update_cache(cache_path)

    fired = _display_update_notification(env.container, cache_path)

    captured = capsys.readouterr()
    assert "new version" in captured.out.lower(), (
        f"The update notification must fire; got: {captured.out!r}"
    )
    assert fired == ["checks.update"], (
        f"A fired update check must report 'checks.update'; got: {fired!r}"
    )


def test_update_notification_returns_empty_when_no_update_available(
    env, capsys, tmp_path
):
    # No cache (or a stale/older cache) means no notification fires, so the
    # helper must report NO fired check.
    config = env.mock_port(IConfigService)
    config.get_setting.side_effect = lambda key, default=None: default
    cache_path = tmp_path / ".update_cache.json"  # absent -> no cache

    fired = _display_update_notification(env.container, cache_path)

    captured = capsys.readouterr()
    assert "new version" not in captured.out.lower(), (
        f"No update must be displayed; got: {captured.out!r}"
    )
    assert fired == [], (
        f"An absent update cache must not report a fired check; got: {fired!r}"
    )


def test_footer_is_silent_when_no_check_fired(capsys):
    # No check fired -> the shared footer is a pure no-op (no line printed).
    _display_checks_footer([])

    captured = capsys.readouterr()
    assert captured.out == "", (
        f"An empty fired-keys list must print no footer; got: {captured.out!r}"
    )


def test_footer_names_a_single_fired_check_with_singular_wording(capsys):
    # Exactly one check fired -> the singular "this check" footer naming the key.
    _display_checks_footer(["checks.templates"])

    captured = capsys.readouterr()
    assert captured.out == (
        "You can disable this check in .teddy/config.yaml: checks.templates.\n"
    ), f"Singular footer wording mismatch; got: {captured.out!r}"


def test_footer_names_multiple_fired_checks_in_canonical_order(capsys):
    # Multiple checks fired -> the plural footer, with the keys deduped and
    # ordered by the canonical sequence regardless of the reported order.
    _display_checks_footer(["checks.update", "checks.templates", "checks.prompts"])

    captured = capsys.readouterr()
    assert captured.out == (
        "You can disable these checks in .teddy/config.yaml: "
        "checks.prompts, checks.templates, checks.update.\n"
    ), f"Plural footer wording/order mismatch; got: {captured.out!r}"


def test_footer_dedupes_repeated_fired_keys(capsys):
    # A repeated fired key must collapse to a single entry (and stay singular).
    _display_checks_footer(["checks.update", "checks.update"])

    captured = capsys.readouterr()
    assert captured.out == (
        "You can disable this check in .teddy/config.yaml: checks.update.\n"
    ), f"Duplicate fired keys must be deduped; got: {captured.out!r}"
