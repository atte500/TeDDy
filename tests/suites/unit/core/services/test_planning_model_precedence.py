"""Precedence and metadata-separation coverage for ``PlanningService``.

The effective model resolves from the explicit ``--model`` override (persisted as
``model_override``), then the persona entry, then the global ``llm.model``. The
per-turn ``model`` key is display data only; a carried value must never become a
resolution input, so a persona switched on resume re-resolves every turn.
"""

from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.domain.models.planning_ports import PlanningPorts
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.outbound import (
    IConfigService,
    IFileSystemManager,
    ILlmClient,
    IUserInteractor,
    ISessionManager,
)
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.services.planning_service import PlanningService
from tests.harness.setup.mocking import POSIXPathMock


def _response(content="# Plan\n## Action Plan\n### EXECUTE\necho 1"):
    choice = POSIXPathMock()
    choice.message.content = content
    response = POSIXPathMock()
    response.choices = [choice]
    response.model = "served-model"
    return response


def _build(env, *, agents, global_model, meta):
    config = env.mock_port(IConfigService)

    def _get_setting(key, default=None):
        if key == "agents":
            return agents
        if key == "llm.model":
            return global_model
        if key == "llm.max_retries":
            return 1
        return default

    config.get_setting.side_effect = _get_setting

    llm = env.mock_port(ILlmClient)
    llm.validate_config.return_value = []
    llm.get_completion.return_value = _response()
    llm.get_token_count.return_value = 10
    llm.get_text_token_count.return_value = 5
    llm.get_context_window.return_value = 128000
    llm.get_completion_cost.return_value = 0.0

    prompt = env.mock_port(IPromptManager)
    prompt.resolve_message.return_value = "msg"
    prompt.resolve_agent_metadata.return_value = ("architect", dict(meta), "meta.yaml")
    prompt.fetch_system_prompt.return_value = "sys"
    prompt.log_telemetry.return_value = 0.0

    context = env.mock_port(IGetContextUseCase)
    context.get_context.return_value = ProjectContext(
        header="H", content="C", scoped_paths={}, git_status=""
    )

    ui = env.mock_port(IUserInteractor)
    env.mock_port(IFileSystemManager)
    env.mock_port(ISessionManager)

    env.container.register(
        PlanningPorts,
        factory=lambda: PlanningPorts(
            context=env.container.resolve(IGetContextUseCase),
            llm=env.container.resolve(ILlmClient),
            fs=env.container.resolve(IFileSystemManager),
            config=env.container.resolve(IConfigService),
            prompts=env.container.resolve(IPromptManager),
            ui=env.container.resolve(IUserInteractor),
            session_manager=env.container.resolve(ISessionManager),
        ),
    )
    env.container.register(PlanningService)
    return env.get_service(PlanningService), llm, ui


def _completion_model(llm):
    return llm.get_completion.call_args[1]["model"]


def test_model_override_outranks_persona_and_global(env):
    """A persisted ``--model`` override beats the persona and the global model."""
    service, llm, _ui = _build(
        env,
        agents={"architect": {"model": "persona/model"}},
        global_model="global/model",
        meta={"model_override": "flag/model"},
    )

    service.generate_plan(user_message="x", turn_dir="01", context_files={})

    assert _completion_model(llm) == "flag/model"


def test_persona_re_resolves_ignoring_carried_effective_model(env):
    """A carried ``model`` is display data, so a switched persona re-resolves."""
    service, llm, _ui = _build(
        env,
        agents={"architect": {"model": "persona/model"}},
        global_model="global/model",
        meta={"model": "carried/old-model"},
    )

    service.generate_plan(user_message="x", turn_dir="01", context_files={})

    assert _completion_model(llm) == "persona/model"


def test_global_used_when_no_override_and_no_persona(env):
    """With neither an override nor a persona, the global model is used."""
    service, llm, _ui = _build(
        env,
        agents={},
        global_model="global/model",
        meta={"model": "carried/old-model"},
    )

    service.generate_plan(user_message="x", turn_dir="01", context_files={})

    assert _completion_model(llm) == "global/model"


def test_fresh_turn_telemetry_shows_the_effective_persona_model(env):
    """The fresh turn's telemetry repeats the effective persona model."""
    service, _llm, ui = _build(
        env,
        agents={"architect": {"model": "persona/model"}},
        global_model="global/model",
        meta={},
    )

    service.generate_plan(user_message="x", turn_dir="01", context_files={})

    displayed = [call.args[0] for call in ui.display_message.call_args_list]
    assert any("• Model:" in line and "persona/model" in line for line in displayed)


def test_effective_model_reaches_the_token_count(env):
    """Token counting runs against the effective persona model, not the global one."""
    service, llm, _ui = _build(
        env,
        agents={"architect": {"model": "persona/model"}},
        global_model="global/model",
        meta={},
    )

    service.generate_plan(user_message="x", turn_dir="01", context_files={})

    assert llm.get_token_count.call_args.kwargs.get("model") == "persona/model"
