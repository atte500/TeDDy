"""Regression pin for the removal of the deprecated ``ConsolePlanReviewer`` adapter.

This Poka-Yoke guard ensures the console plan reviewer (the
``teddy_executor.adapters.inbound.console_plan_reviewer`` module) cannot silently
re-appear once the Textual TUI has become the sole plan reviewer.
"""

import importlib.util


def test_console_plan_reviewer_module_is_removed():
    assert (
        importlib.util.find_spec(
            "teddy_executor.adapters.inbound.console_plan_reviewer"
        )
        is None
    ), "The deprecated ConsolePlanReviewer adapter module must remain deleted."
