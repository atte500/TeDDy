"""Proof MRE: replica adapter prefers OpenRouter's BYOK upstream cost.

Keeps the same hermetic shape as `01-openrouter-byok-cost-display-mre.py` but
imports the replica adapter instead of production, and adds the two shapes that
motivate the fix: a BYOK request whose OpenRouter fee is waived (0) while the
upstream spend is positive, and a non-BYOK request whose fee is positive while
the upstream field is 0.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from replica_litellm_adapter import FixedLiteLLMAdapter

CONFIGURED = "openrouter/anthropic/claude-sonnet-4"
SERVED = "anthropic/claude-sonnet-4"
PRICE = {"input_cost_per_token": 3e-06, "output_cost_per_token": 1.5e-05}
PRICED_ROW = {**PRICE, "max_input_tokens": 200000}


class FakeConfig:
    def get_setting(self, key, default=None):
        values = {"llm.model": CONFIGURED, "llm.max_retries": 3}
        return values.get(key, default)


class FakeLitellm:
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


def make_adapter(model_cost):
    return FixedLiteLLMAdapter(
        config_service=FakeConfig(),
        hydrator=None,
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


def make_response(model, hidden_params=None, usage=None):
    return SimpleNamespace(
        model=model, _hidden_params=hidden_params or {}, usage=usage
    )


def run_case(name, *, model_cost, meta, completion_response, expected_cost):
    adapter = make_adapter(model_cost)
    cost = adapter.get_completion_cost(completion_response, model_override=CONFIGURED)
    recorded = getattr(completion_response, "_teddy_cost_recorded", False)
    ui = RecordingInteractor()
    build_planning_service(adapter, ui)._display_telemetry(meta, token_count=1000)
    panel = ui.last_cost_line()
    status = "PASS" if abs(cost - expected_cost) < 1e-9 else "FAIL"
    print(f"[{status}] {name}")
    print(f"       cost={cost!r} (expected {expected_cost!r}) recorded={recorded!r}")
    print(f"       display={panel}")
    return status


def main():
    print(f"CONFIGURED={CONFIGURED}\nSERVED={SERVED}\n")

    results = []

    # BYOK: OpenRouter waives the 5% fee (usage.cost = 0) and reports the real
    # provider spend in cost_details.upstream_inference_cost.
    results.append(
        run_case(
            "BYOK: fee=0, upstream>0",
            model_cost={CONFIGURED: PRICED_ROW},
            meta={
                "model": CONFIGURED,
                "actual_model": SERVED,
                "cumulative_cost": 0.0,
                "cost_recorded": True,
            },
            completion_response=make_response(
                SERVED,
                {"response_cost": 0.0},
                usage=SimpleNamespace(
                    prompt_tokens=1000,
                    completion_tokens=500,
                    cost=0.0,
                    cost_details={"upstream_inference_cost": 0.0061},
                ),
            ),
            expected_cost=0.0061,
        )
    )

    # Non-BYOK OpenRouter: the fee is OpenRouter's actual charge; the upstream
    # field is 0 per OpenRouter docs, so the reported fee must remain authoritative.
    results.append(
        run_case(
            "non-BYOK: fee>0, upstream=0",
            model_cost={CONFIGURED: PRICED_ROW},
            meta={
                "model": CONFIGURED,
                "actual_model": SERVED,
                "cumulative_cost": 0.0,
                "cost_recorded": True,
            },
            completion_response=make_response(
                SERVED,
                {"response_cost": 0.0105},
                usage=SimpleNamespace(
                    prompt_tokens=1000,
                    completion_tokens=500,
                    cost=0.0105,
                    cost_details={"upstream_inference_cost": 0.0},
                ),
            ),
            expected_cost=0.0105,
        )
    )

    # A shape without cost_details (older litellm, non-OpenRouter provider) must
    # keep the production behavior: prefer the hidden reported cost.
    results.append(
        run_case(
            "no cost_details: reported cost preserved",
            model_cost={CONFIGURED: PRICED_ROW},
            meta={
                "model": CONFIGURED,
                "actual_model": SERVED,
                "cumulative_cost": 0.0,
                "cost_recorded": True,
            },
            completion_response=make_response(
                SERVED,
                {"response_cost": 0.0021},
                usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=500),
            ),
            expected_cost=0.0021,
        )
    )

    print()
    print("ALL PASS" if all(r == "PASS" for r in results) else "FAILURES DETECTED")


if __name__ == "__main__":
    main()
