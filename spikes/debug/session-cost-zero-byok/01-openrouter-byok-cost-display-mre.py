"""MRE: which OpenRouter response shapes leave the session-cost panel at $0.0000?

Drives the REAL LiteLLMAdapter cost extraction and the REAL
PlanningService._display_telemetry gate. A fake litellm module supplies only the
registry lookups and the recompute the chain touches, so the probe is hermetic
and never reaches the network.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter

CONFIGURED = "openrouter/anthropic/claude-sonnet-4"
SERVED = "anthropic/claude-sonnet-4"
PRICE = {"input_cost_per_token": 3e-06, "output_cost_per_token": 1.5e-05}
PRICED_ROW = {**PRICE, "max_input_tokens": 200000}
USAGE = SimpleNamespace(prompt_tokens=1000, completion_tokens=500)
HYDRATED = {"context_window": 200000, "pricing": dict(PRICE)}


class FakeConfig:
    def get_setting(self, key, default=None):
        values = {"llm.model": CONFIGURED, "llm.max_retries": 3}
        return values.get(key, default)


class FakeHydrator:
    """Returns fixed metadata, or None to model a hydration miss."""

    def __init__(self, metadata):
        self._metadata = metadata
        self.calls = []

    def get_metadata(self, model_id):
        self.calls.append(model_id)
        return self._metadata


class FakeLitellm:
    """Stand-in for the litellm surface the cost chain touches."""

    def __init__(self, model_cost):
        self.model_cost = model_cost
        self.completion_cost_models = []

    def completion_cost(self, completion_response=None, **kwargs):
        model = str(getattr(completion_response, "model", None))
        self.completion_cost_models.append(model)
        info = self.model_cost.get(model)
        if not info or "input_cost_per_token" not in info:
            raise Exception(f"This model isn't mapped yet. model={model}")
        usage = getattr(completion_response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        return float(
            prompt_tokens * info["input_cost_per_token"]
            + completion_tokens * info.get("output_cost_per_token", 0.0)
        )

    def token_counter(self, model=None, messages=None):
        return 1000


class RecordingInteractor:
    def __init__(self):
        self.messages = []

    def display_message(self, message):
        self.messages.append(message)

    def last_cost_line(self):
        for message in reversed(self.messages):
            if "Session Cost:" in message:
                return message.strip()
        return "<no telemetry emitted>"


def make_adapter(model_cost, hydrator=None):
    return LiteLLMAdapter(
        config_service=FakeConfig(),
        hydrator=hydrator,
        _litellm_provider=FakeLitellm(model_cost),
    )


def build_planning_service(llm, ui):
    from teddy_executor.core.domain.models.planning_ports import PlanningPorts
    from teddy_executor.core.services.planning_service import PlanningService

    ports = {field.name: None for field in dataclasses.fields(PlanningPorts)}
    for name in ports:
        if name in {"llm", "llm_client"}:
            ports[name] = llm
        elif name in {"ui", "user_interactor"}:
            ports[name] = ui
        elif name in {"config", "config_service"}:
            ports[name] = FakeConfig()
    return PlanningService(PlanningPorts(**ports))


def make_response(model, hidden_params=None, usage=USAGE):
    return SimpleNamespace(
        model=model, _hidden_params=hidden_params or {}, usage=usage
    )


def run_case(name, *, model_cost, hydrator, meta, completion_response):
    adapter = make_adapter(model_cost, hydrator)
    cost = adapter.get_completion_cost(completion_response, model_override=CONFIGURED)
    recorded = getattr(completion_response, "_teddy_cost_recorded", False)
    ui = RecordingInteractor()
    build_planning_service(adapter, ui)._display_telemetry(meta, token_count=1000)
    print(f"[CASE] {name}")
    print(f"       cost={cost!r} recorded={recorded!r}")
    print(f"       priced_identities={adapter._get_litellm().completion_cost_models}")
    print(f"       display={ui.last_cost_line()}")
    return cost, recorded, ui.last_cost_line()


def main():
    print(f"CONFIGURED={CONFIGURED}\nSERVED={SERVED}\n")

    # 1. Adapter-level: the provider reports a cost directly on the response.
    run_case(
        "1 reported response_cost (paid model)",
        model_cost={SERVED: PRICED_ROW, CONFIGURED: PRICED_ROW},
        hydrator=None,
        meta={"model": CONFIGURED, "actual_model": SERVED,
              "cumulative_cost": 0.0012345, "cost_recorded": True},
        completion_response=make_response(
            SERVED, {"response_cost": 0.0012345}
        ),
    )

    # 2. First turn: telemetry runs BEFORE the completion, so it prints the
    #    inherited cumulative cost. A nonzero turn cost is deliberately given to
    #    show the figure the panel cannot yet know about.
    run_case(
        "2 first-turn telemetry (pre-response cumulative)",
        model_cost={CONFIGURED: PRICED_ROW},
        hydrator=FakeHydrator(HYDRATED),
        meta={"model": CONFIGURED, "cumulative_cost": 0.0},
        completion_response=make_response(SERVED, {"response_cost": 0.004}),
    )

    # 3. Header-only reported cost (no _hidden_params["response_cost"]).
    run_case(
        "3 header-only reported cost",
        model_cost={SERVED: PRICED_ROW, CONFIGURED: PRICED_ROW},
        hydrator=None,
        meta={"model": CONFIGURED, "actual_model": SERVED,
              "cumulative_cost": 0.0021, "cost_recorded": True},
        completion_response=make_response(
            SERVED,
            {"additional_headers": {"llm_provider-x-litellm-response-cost": 0.0021}},
        ),
    )

    # 4. A genuinely reported zero (free model): recorded but unpriced.
    run_case(
        "4 reported 0.0 (free model)",
        model_cost={SERVED: {"max_input_tokens": 128000}},
        hydrator=None,
        meta={"model": CONFIGURED, "actual_model": SERVED,
              "cumulative_cost": 0.0, "cost_recorded": True},
        completion_response=make_response(SERVED, {"response_cost": 0.0}),
    )

    # 5. No reported cost, served identity unmapped, hydration misses: the
    #    recompute fails and falls back to an UNMARKED 0.0. On turn >= 2 the
    #    display model is the served id, which is not in the registry.
    run_case(
        "5 unmapped + hydration miss, turn >= 2 (actual_model known)",
        model_cost={CONFIGURED: PRICED_ROW},
        hydrator=FakeHydrator(None),
        meta={"model": CONFIGURED, "actual_model": SERVED,
              "cumulative_cost": 0.0, "cost_recorded": False},
        completion_response=make_response(SERVED, {}),
    )

    # 5b. Same failure, but before actual_model is persisted: the display model
    #     is the hydrated configured id, so supports_pricing says True.
    run_case(
        "5b unmapped + hydration miss, configured model displayed",
        model_cost={CONFIGURED: PRICED_ROW},
        hydrator=FakeHydrator(None),
        meta={"model": CONFIGURED, "cumulative_cost": 0.0},
        completion_response=make_response(SERVED, {}),
    )

    # 6. No reported cost, served identity unmapped, hydration succeeds: the
    #    adapter injects pricing for both candidates and the recompute runs.
    run_case(
        "6 unmapped + hydration success",
        model_cost={CONFIGURED: PRICED_ROW},
        hydrator=FakeHydrator(HYDRATED),
        meta={"model": CONFIGURED, "actual_model": SERVED,
              "cumulative_cost": 0.003, "cost_recorded": True},
        completion_response=make_response(SERVED, {}),
    )

    # 7. Truly unpriced model, nothing recorded: the placeholder must appear.
    run_case(
        "7 unpriced model, nothing recorded",
        model_cost={CONFIGURED: {"max_input_tokens": 128000}},
        hydrator=None,
        meta={"model": CONFIGURED, "cumulative_cost": 0.0, "cost_recorded": False},
        completion_response=make_response(
            CONFIGURED, {"response_cost": 0.0}
        ),
    )


if __name__ == "__main__":
    main()
