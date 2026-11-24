import pytest
from types import SimpleNamespace

from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound import IUserInteractor
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.services.planning_service import PlanningService


def _session_cost_line(display_calls):
    return next(c for c in display_calls if "• Session Cost:" in c)


@pytest.mark.parametrize(
    "case",
    [
        (
            {
                "cumulative_cost": 0.05,
                "cumulative_prompt_tokens": 1000,
                "cumulative_cached_tokens": 600,
                "model": "gpt-4o",
            },
            128000,
            True,
            "$0.0500 (60% cached)",
            True,
        ),
        (
            {
                "cumulative_cost": 0.05,
                "cumulative_prompt_tokens": 1000,
                "cumulative_cached_tokens": 0,
                "model": "gpt-4o",
            },
            128000,
            True,
            "$0.0500",
            False,
        ),
        (
            {
                "cumulative_cost": 0.05,
                "cumulative_prompt_tokens": 1000,
                "cumulative_cached_tokens": 2000,
                "model": "gpt-4o",
            },
            128000,
            True,
            "$0.0500 (100% cached)",
            True,
        ),
        (
            {
                "cumulative_cost": 0.05,
                "cumulative_prompt_tokens": 3000,
                "cumulative_cached_tokens": 1000,
                "model": "gpt-4o",
            },
            128000,
            True,
            "$0.0500 (33% cached)",
            True,
        ),
        (
            {
                "cumulative_cost": 0.05,
                "cumulative_prompt_tokens": 0,
                "cumulative_cached_tokens": 500,
                "model": "gpt-4o",
            },
            128000,
            True,
            "$0.0500",
            False,
        ),
        (
            {"cumulative_cost": 0.05, "model": "gpt-4o"},
            128000,
            True,
            "$0.0500",
            False,
        ),
        (
            {
                "cumulative_cost": 0.0,
                "cumulative_prompt_tokens": 1000,
                "cumulative_cached_tokens": 600,
                "model": "unknown-model",
            },
            128000,
            False,
            "$???",
            False,
        ),
        (
            {
                "cumulative_cost": 0.0,
                "cumulative_prompt_tokens": 1000,
                "cumulative_cached_tokens": 600,
                "model": "free-model",
                "cost_recorded": True,
            },
            128000,
            False,
            "$0.0000",
            False,
        ),
    ],
    ids=[
        "cached-hit",
        "zero-cache",
        "clamp-at-100",
        "rounds-to-integer",
        "zero-denominator",
        "no-cumulative-keys",
        "unknown-pricing",
        "free-model-zero-cost",
    ],
)
def test_session_cost_suffix_follows_the_cache_ratio(env, case):
    meta, context_window, supports_pricing, expected_fragment, has_suffix = case
    mock_ui = env.mock_port(IUserInteractor)
    mock_llm = env.mock_port(ILlmClient)
    mock_prompt = env.mock_port(IPromptManager)
    env.mock_port(IGetContextUseCase).get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}
    )

    mock_prompt.resolve_message.return_value = "test"
    mock_prompt.resolve_agent_metadata.return_value = ("pathfinder", meta, "meta.yaml")
    mock_llm.get_token_count.return_value = 1000
    mock_llm.get_context_window.return_value = context_window
    mock_llm.supports_pricing.return_value = supports_pricing
    mock_llm.get_completion.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="# Mock Plan\n"),
                finish_reason="stop",
            )
        ],
        model="gpt-4o",
    )
    mock_llm.get_completion_cost.return_value = 0.0

    service = env.get_service(PlanningService)
    service.generate_plan(user_message="test", turn_dir="turns/01")

    calls = [call[0][0] for call in mock_ui.display_message.call_args_list]
    line = _session_cost_line(calls)

    assert expected_fragment in line
    assert ("% cached" in line) is has_suffix
