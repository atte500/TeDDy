import typing

from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase


class TestIRunPlanUseCaseContract:
    """Contract tests for IRunPlanUseCase."""

    def test_resume_returns_tuple_with_session_name_and_report(self):
        """resume() must return (actual_session_name, report) tuple."""
        annotations = IRunPlanUseCase.resume.__annotations__
        assert "return" in annotations, "resume() must have a return type annotation"

        return_type = annotations["return"]

        # Check that the return type is a tuple[str, Optional[ExecutionReport]]
        origin = typing.get_origin(return_type)
        args = typing.get_args(return_type)

        assert origin is tuple, f"Expected return type to be tuple, got {origin}"
        assert len(args) == 2, f"Expected 2 tuple elements, got {len(args)}"

        # First element must be str
        first, second = args
        assert first is str, f"First tuple element should be str, got {first}"

        # Second element must be Optional[ExecutionReport]
        # Optional[X] is Union[X, None] at runtime
        second_origin = typing.get_origin(second)
        second_args = typing.get_args(second)
        assert second_origin is typing.Union, (
            f"Second element should be Union[ExecutionReport, None], "
            f"got origin={second_origin}"
        )
        assert type(None) in second_args, "Second element must include None (Optional)"

        non_none_types = [t for t in second_args if t is not type(None)]
        assert len(non_none_types) == 1, (
            f"Expected exactly one non-None type in Optional, got {len(non_none_types)}"
        )
        assert non_none_types[0] is ExecutionReport, (
            f"Second element should wrap ExecutionReport, got {non_none_types[0]}"
        )
