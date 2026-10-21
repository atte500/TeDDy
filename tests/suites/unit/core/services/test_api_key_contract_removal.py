"""Contract invariants: the API-key override chain is gone from the core.

The command-line option and the inbound handler plumbing were removed earlier.
This module pins the remaining core contract: ``SessionOptions`` carries no key
field, and the planning retry helper accepts no key argument. Together they stop
the completion override path from reappearing as a plaintext key route.
"""

import inspect
from dataclasses import fields

from teddy_executor.core.domain.models.session import SessionOptions
from teddy_executor.core.services.planning_service import PlanningService


def test_session_options_declares_no_api_key_field():
    """The session options dataclass exposes no ``api_key`` field."""
    field_names = {field.name for field in fields(SessionOptions)}

    assert "api_key" not in field_names


def test_planning_retry_helper_declares_no_api_key_parameter():
    """The planning retry helper exposes no ``api_key`` parameter."""
    parameters = inspect.signature(
        PlanningService._perform_generation_with_retry
    ).parameters

    assert "api_key" not in parameters
