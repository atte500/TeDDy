"""Integration: the guardrails namespace is renamed from yolo_guardrails.

The bundled config declares the renamed ``guardrails`` namespace with the raised
150-turn default, and the production guard's turn-limit message names the
renamed keys. The legacy ``yolo_guardrails`` fallback read stays for existing
user configs, so this suite asserts only that the SHIPPED namespace and the
user-facing message use the renamed name.

The reason assertion is quote-delimited on purpose: the bare string
``guardrails.max_turns`` is a substring of the legacy ``yolo_guardrails.max_turns``,
so a naive containment check would pass even with the old name.
"""

from importlib import resources
from unittest.mock import create_autospec

import yaml

from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.services.session_loop_guard import ProductionSessionLoopGuard


def _load_bundled_config() -> dict:
    """Load the bundled config.yaml as a parsed mapping via the package resource."""
    resource = resources.files("teddy_executor.resources.config").joinpath(
        "config.yaml"
    )
    return yaml.safe_load(resource.read_text(encoding="utf-8"))


def test_bundled_config_declares_the_renamed_guardrails_namespace():
    """The bundled config declares ``guardrails`` and no legacy ``yolo_guardrails``."""
    config = _load_bundled_config()

    guardrails = config.get("guardrails")
    assert isinstance(guardrails, dict), (
        "Bundled config.yaml must declare the renamed 'guardrails' block, "
        f"got: {guardrails!r}"
    )
    assert guardrails.get("max_turns") == 150, (
        "Bundled guardrails.max_turns must match the raised 150 default, "
        f"got: {guardrails.get('max_turns')!r}"
    )
    assert "yolo_guardrails" not in config, (
        "Bundled config.yaml must NOT declare the legacy 'yolo_guardrails' block"
    )


def test_guard_limit_message_names_the_renamed_guardrails_key():
    """The guard's turn-limit message names ``'guardrails.max_turns'``."""
    config = create_autospec(IConfigService)
    config.get_setting.side_effect = lambda key, default=None: (
        1 if key == "guardrails.max_turns" else default
    )
    config.get_config_path.return_value = ".teddy/config.yaml"

    environment = create_autospec(ISystemEnvironment)
    environment.get_env.return_value = None

    guard = ProductionSessionLoopGuard(
        config_service=config,
        system_environment=environment,
        initial_turn=0,
        initial_cost=0.0,
    )

    should_continue, reason = guard.should_continue(1, 0.0, False)

    assert should_continue is False
    assert "'guardrails.max_turns'" in reason, (
        f"Reason must name the renamed config key, got: {reason!r}"
    )
    assert "yolo_guardrails" not in reason, (
        f"Reason must not name the legacy namespace, got: {reason!r}"
    )
