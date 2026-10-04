"""Unit tests for the configurable ``yolo_default`` feature.

This file hosts the feature's unit-level contracts: the shipped configuration
surface (the ``yolo_default`` key in the bundled template) and the full
tri-state resolution matrix of the single-sourced ``_resolve_yolo`` helper.
"""

from importlib.resources import files
from unittest.mock import Mock

import pytest
import yaml

from teddy_executor.__main__ import _resolve_yolo
from teddy_executor.core.ports.outbound.config_service import IConfigService


def test_shipped_config_template_declares_yolo_default_false():
    """Contract: the shipped config template declares a top-level ``yolo_default: false``.

    Guards the shipped configuration surface so a fresh ``teddy init`` always
    materialises the key (and its explanatory comment), rather than relying
    solely on the code-level fallback that keeps pre-existing configs working.
    """
    template = files("teddy_executor.resources.config").joinpath("config.yaml")
    data = yaml.safe_load(template.read_text(encoding="utf-8"))

    assert "yolo_default" in data, (
        "The shipped config template must declare a top-level 'yolo_default' key."
    )
    assert data["yolo_default"] is False, (
        "The shipped 'yolo_default' default must be False."
    )


def _config_service(value: bool) -> Mock:
    """Build a bound ``IConfigService`` double whose ``get_setting`` yields ``value``."""
    service = Mock(spec=IConfigService)
    service.get_setting.side_effect = lambda key, default=None: value
    return service


@pytest.mark.parametrize(
    ("flag", "config_value", "expected"),
    [
        (None, False, False),  # unset flag + config off -> off
        (None, True, True),  # unset flag + config on -> on
        (True, False, True),  # explicit --yolo wins over config off
        (True, True, True),  # explicit --yolo wins over config on
        (False, False, False),  # explicit --no-yolo wins over config off
        (False, True, False),  # explicit --no-yolo wins over config on
    ],
)
def test_resolve_yolo_resolution_matrix(flag, config_value, expected):
    """The tri-state flag resolves an unset value against ``yolo_default``."""
    service = _config_service(config_value)

    assert _resolve_yolo(flag, service) is expected


def test_resolve_yolo_never_consults_config_when_flag_is_explicit():
    """An explicit flag must win without consulting the config service."""
    service = _config_service(True)

    assert _resolve_yolo(False, service) is False
    service.get_setting.assert_not_called()
