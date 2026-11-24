import yaml
import pytest

from teddy_executor.core.domain.models.token_usage import TokenUsage
from teddy_executor.core.ports.outbound import ILlmClient
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.fake_llm_client import FakeLlmClient

PLAN_CONTENT = (
    "# Mock Plan\n\n## Action Plan\n### READ\n- Resource: [README.md](/README.md)\n"
)


@pytest.mark.parametrize(
    ("usages", "expected_prompt_tokens", "expected_cached_tokens"),
    [
        ([TokenUsage(prompt_tokens=1234, cached_tokens=0)], 1234, 0),
        ([], 0, 0),
    ],
    ids=["provider-usage", "no-provider-usage"],
)
def test_first_turn_persists_integer_usage_without_a_cache_suffix(
    monkeypatch,
    real_env,
    usages,
    expected_prompt_tokens,
    expected_cached_tokens,
):
    real_env.container.register(
        ILlmClient,
        instance=FakeLlmClient(usages=usages, completion_content=PLAN_CONTENT),
    )
    (real_env.workspace / "README.md").write_text("hello\n", encoding="utf-8")
    cli = CliTestAdapter(monkeypatch, real_env.workspace)

    result = cli.run_start(["-y", "-m", "smoke check"])

    meta_path = next(real_env.workspace.glob(".teddy/sessions/*/01/meta.yaml"))
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))

    assert meta["prompt_tokens"] == expected_prompt_tokens
    assert meta["cached_tokens"] == expected_cached_tokens
    assert isinstance(meta["prompt_tokens"], int)
    assert isinstance(meta["cached_tokens"], int)
    assert meta["cumulative_prompt_tokens"] == 0
    assert meta["cumulative_cached_tokens"] == 0
    assert isinstance(meta["cumulative_prompt_tokens"], int)
    assert isinstance(meta["cumulative_cached_tokens"], int)
    assert "Session Cost" in result.stdout
    assert "% cached" not in result.stdout
