"""Unit tests: the waiting bracketing around the model call.

``PlanningService`` brackets its retry loop with ``begin_waiting`` and a
``finally``-guarded ``end_waiting``, so an adapter renders activity for exactly
the duration of the completion and the wait always ends: on the first
successful attempt, across a retry, and when the completion raises. The label
names the persona that is answering, so the transient line stays informative
without repeating the turn/session banner above it.
"""

from typing import Any

import pytest

from teddy_executor.core.domain.models.planning_ports import PlanningPorts
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.services.planning_service import PlanningService
from tests.harness.setup.mocking import (
    POSIXPathMock,
    completion_response,
    register_mock,
)

AGENT = "pathfinder"
EXPECTED_LABEL = f"Waiting for {AGENT} to respond..."
PLAN_CONTENT = "# Plan\nContent"


def _register_llm(container: Any, max_retries: int = 3) -> POSIXPathMock:
    """Register the config and LLM doubles the retry loop reads.

    Registration precedes graph resolution, because building the graph reads
    the config through the tree generator.
    """
    mock_config = register_mock(container, IConfigService)
    mock_llm = register_mock(container, ILlmClient)
    mock_config.get_setting.side_effect = lambda key, default=None: (
        max_retries if key == "llm.max_retries" else default
    )
    mock_llm.get_completion_cost.return_value = 0.0
    return mock_llm


def _service(env: Any, max_retries: int = 3) -> tuple[PlanningService, POSIXPathMock]:
    """Arrange the planning graph whose completion answers successfully."""
    mock_llm = _register_llm(env.container, max_retries=max_retries)
    mock_llm.get_completion.return_value = completion_response(PLAN_CONTENT)
    return PlanningService(env.container.resolve(PlanningPorts)), mock_llm


def _run_generation(service: PlanningService) -> None:
    """Drive the retry loop as the responding agent."""
    service._perform_generation_with_retry(
        messages=[], model="test-model", agent_name=AGENT
    )


def _record_wait_order(interactor: POSIXPathMock, order: list[str]) -> None:
    """Record the bracketing order the indicator observes."""
    interactor.begin_waiting.side_effect = lambda _message: order.append("begin")
    interactor.end_waiting.side_effect = lambda: order.append("end")


def _assert_single_wait(interactor: POSIXPathMock) -> None:
    """Assert exactly one labelled wait wrapped the completion."""
    interactor.begin_waiting.assert_called_once_with(EXPECTED_LABEL)
    interactor.end_waiting.assert_called_once_with()


def test_the_wait_brackets_the_completion_call(env: Any) -> None:
    order: list[str] = []
    service, mock_llm = _service(env)

    def _complete(**_kwargs: Any) -> POSIXPathMock:
        order.append("completion")
        return completion_response(PLAN_CONTENT)

    mock_llm.get_completion.side_effect = _complete

    interactor = env.get_mock_user_interactor()
    _record_wait_order(interactor, order)

    # Act
    _run_generation(service)

    # Assert: the region opens before the call and closes after it.
    assert order == ["begin", "completion", "end"]


def test_the_wait_label_names_the_responding_agent(env: Any) -> None:
    service, _ = _service(env)
    interactor = env.get_mock_user_interactor()

    # Act
    _run_generation(service)

    # Assert: the core owns the wording, the adapter owns how it is drawn.
    interactor.begin_waiting.assert_called_once_with(EXPECTED_LABEL)


def test_the_wait_ends_when_the_completion_raises(env: Any) -> None:
    service, mock_llm = _service(env)
    mock_llm.get_completion.side_effect = RuntimeError("primary endpoint unreachable")

    interactor = env.get_mock_user_interactor()

    # Act / Assert: the error reaches the caller unchanged.
    with pytest.raises(RuntimeError):
        _run_generation(service)

    # Assert: the region closed first, so the traceback cannot interleave with
    # the animation.
    _assert_single_wait(interactor)


def test_a_retry_stays_inside_one_wait(env: Any) -> None:
    order: list[str] = []
    service, mock_llm = _service(env)

    empty_response = POSIXPathMock()
    empty_response.choices = []
    mock_llm.get_completion.side_effect = [
        empty_response,
        completion_response(PLAN_CONTENT),
    ]

    interactor = env.get_mock_user_interactor()
    _record_wait_order(interactor, order)

    # Act
    _run_generation(service)

    # Assert: one region covers every attempt, so the indicator never flickers
    # between the retry notice and the next completion.
    assert mock_llm.get_completion.call_count == 2
    assert order == ["begin", "end"]
    _assert_single_wait(interactor)
