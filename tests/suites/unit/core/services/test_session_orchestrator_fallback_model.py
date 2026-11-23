"""Unit coverage: the fallback context path threads the effective model.

A session turn that arrives without a planning-gathered context falls back to
``_gather_fallback_context``. That path must count tokens and resolve the
context window against the same effective model the planner uses: the turn's
explicit ``model_override``, then the persona entry, then the global
``llm.model``. The carried ``model`` key is display data only and never a
resolution input.
"""

from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound import (
    IConfigService,
    ILlmClient,
    ISessionManager,
)
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator

PLAN_PATH = ".teddy/sessions/20260101_120000-demo/01/plan.md"


class _PlanStub:
    """Minimal plan surface: the fallback path reads ``metadata`` only."""

    def __init__(self, metadata):
        self.metadata = metadata


def _build(env, *, agents, global_model, turn_meta, agent_name="architect"):
    """Construct the orchestrator with spec-bound doubles for the exercised ports."""
    config = env.mock_port(IConfigService)

    def _get_setting(key, default=None):
        if key == "agents":
            return agents
        if key == "llm.model":
            return global_model
        return default

    config.get_setting.side_effect = _get_setting

    session = env.mock_port(ISessionManager)
    session.resolve_context_paths.return_value = {}
    session.load_turn_meta.return_value = dict(turn_meta)

    llm = env.mock_port(ILlmClient)
    llm.get_context_window.return_value = 128000
    llm.get_text_token_count.return_value = 5

    prompt = env.mock_port(IPromptManager)
    prompt.fetch_system_prompt.return_value = "sys"

    context = env.mock_port(IGetContextUseCase)
    context.get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}, agent_name=agent_name
    )

    orchestrator = SessionOrchestrator(
        execution_orchestrator=object(),
        session_service=session,
        file_system_manager=object(),
        plan_validator=object(),
        plan_parser=object(),
        user_interactor=object(),
        lifecycle_manager=object(),
        replanner=object(),
        context_service=context,
        config_service=config,
        llm_client=llm,
        prompt_manager=prompt,
    )
    return orchestrator, llm, context


def _assert_threaded(llm, context, expected):
    """Every consumer in the fallback path receives the effective model."""
    assert llm.get_context_window.call_args.kwargs.get("model") == expected
    assert llm.get_text_token_count.call_args.kwargs.get("model") == expected
    assert context.get_context.call_args.kwargs.get("model") == expected


def test_fallback_context_uses_the_persona_model(env):
    """Without an override, the persona model reaches every consumer."""
    orchestrator, llm, context = _build(
        env,
        agents={"architect": {"model": "persona/model"}},
        global_model="global/model",
        turn_meta={},
    )

    orchestrator._gather_fallback_context(_PlanStub({"Agent": "architect"}), PLAN_PATH)

    _assert_threaded(llm, context, "persona/model")


def test_fallback_context_honours_the_explicit_override(env):
    """A turn's persisted ``model_override`` outranks the persona and global."""
    orchestrator, llm, context = _build(
        env,
        agents={"architect": {"model": "persona/model"}},
        global_model="global/model",
        turn_meta={"model_override": "flag/model"},
    )

    orchestrator._gather_fallback_context(_PlanStub({"Agent": "architect"}), PLAN_PATH)

    _assert_threaded(llm, context, "flag/model")


def test_fallback_context_ignores_the_carried_display_model(env):
    """A carried ``model`` is display data, so the global model resolves."""
    orchestrator, llm, context = _build(
        env,
        agents={},
        global_model="global/model",
        turn_meta={"model": "carried/old-model"},
    )

    orchestrator._gather_fallback_context(_PlanStub({"Agent": "architect"}), PLAN_PATH)

    _assert_threaded(llm, context, "global/model")
