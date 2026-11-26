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
from tests.harness.setup.mocking import POSIXPathMock, register_mock

AGENT = "pathfinder"
EXPECTED_LABEL = f"Waiting for {AGENT} to respond..."


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


def _success_response() -> POSIXPathMock:
    choice = POSIXPathMock()
    choice.message.content = "# Plan\nContent"
    response = POSIXPathMock()
    response.choices = [choice]
    return response


def test_the_wait_brackets_the_completion_call(env: Any) -> None:
    order: list[str] = []
    mock_llm = _register_llm(env.container)

    def _complete(**_kwargs: Any) -> POSIXPathMock:
        order.append("completion")
        return _success_response()

    mock_llm.get_completion.side_effect = _complete

    interactor = env.get_mock_user_interactor()
    interactor.begin_waiting.side_effect = lambda _message: order.append("begin")
    interactor.end_waiting.side_effect = lambda: order.append("end")

    service = PlanningService(env.container.resolve(PlanningPorts))

    # Act
    service._perform_generation_with_retry(
        messages=[], model="test-model", agent_name=AGENT
    )

    # Assert: the region opens before the call and closes after it.
    assert order == ["begin", "completion", "end"]


def test_the_wait_label_names_the_responding_agent(env: Any) -> None:
    mock_llm = _register_llm(env.container)
    mock_llm.get_completion.return_value = _success_response()

    interactor = env.get_mock_user_interactor()
    service = PlanningService(env.container.resolve(PlanningPorts))

    # Act
    service._perform_generation_with_retry(
        messages=[], model="test-model", agent_name=AGENT
    )

    # Assert: the core owns the wording, the adapter owns how it is drawn.
    interactor.begin_waiting.assert_called_once_with(EXPECTED_LABEL)


def test_the_wait_ends_when_the_completion_raises(env: Any) -> None:
    mock_llm = _register_llm(env.container)
    mock_llm.get_completion.side_effect = RuntimeError("primary endpoint unreachable")

    interactor = env.get_mock_user_interactor()
    service = PlanningService(env.container.resolve(PlanningPorts))

    # Act / Assert: the error reaches the caller unchanged.
    with pytest.raises(RuntimeError):
        service._perform_generation_with_retry(
            messages=[], model="test-model", agent_name=AGENT
        )

    # Assert: the region closed first, so the traceback cannot interleave with
    # the animation.
    interactor.begin_waiting.assert_called_once_with(EXPECTED_LABEL)
    interactor.end_waiting.assert_called_once_with()


def test_a_retry_stays_inside_one_wait(env: Any) -> None:
    order: list[str] = []
    mock_llm = _register_llm(env.container, max_retries=3)

    empty_response = POSIXPathMock()
    empty_response.choices = []
    mock_llm.get_completion.side_effect = [empty_response, _success_response()]

    interactor = env.get_mock_user_interactor()
    interactor.begin_waiting.side_effect = lambda _message: order.append("begin")
    interactor.end_waiting.side_effect = lambda: order.append("end")

    service = PlanningService(env.container.resolve(PlanningPorts))

    # Act
    service._perform_generation_with_retry(
        messages=[], model="test-model", agent_name=AGENT
    )

    # Assert: one region covers every attempt, so the indicator never flickers
    # between the retry notice and the next completion.
    assert mock_llm.get_completion.call_count == 2
    assert order == ["begin", "end"]
    assert interactor.begin_waiting.call_count == 1
    assert interactor.end_waiting.call_count == 1
