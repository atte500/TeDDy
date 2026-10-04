"""Unit tests for the configurable ``yolo_default`` feature.

This file hosts the feature's unit-level contracts. It currently covers the
shipped configuration surface (the ``yolo_default`` key in the bundled
template); the resolution-helper matrix is added by a later deliverable.
"""

from importlib.resources import files

import yaml


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
