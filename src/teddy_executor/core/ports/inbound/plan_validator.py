"""
This module defines the inbound port for plan validation.
"""

# Placeholder content
# The Developer will implement this based on the design document.
# See: docs/core/ports/inbound/plan_validator.md

from abc import ABC, abstractmethod


class IPlanValidator(ABC):
    """
    Defines the contract for any service that performs pre-flight validation of a Plan.
    """

    @abstractmethod
    def validate(self, plan) -> list:
        """
        Validates the plan and returns a list of validation errors.
        An empty list signifies a successful validation.
        """
        raise NotImplementedError
