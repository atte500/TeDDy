from types import SimpleNamespace

import pytest

from teddy_executor.core.domain.models.token_usage import TokenUsage
from tests.harness.setup.fake_llm_client import FakeLlmClient


@pytest.mark.parametrize(
    "usage",
    [
        TokenUsage(prompt_tokens=1000, cached_tokens=600),
        TokenUsage(prompt_tokens=1000, cached_tokens=0),
        TokenUsage(),
    ],
    ids=["cached-hit", "zero-cache", "no-usage"],
)
def test_get_token_usage_returns_the_scripted_usage(usage):
    fake = FakeLlmClient(usages=[usage])
    response = SimpleNamespace()

    assert fake.get_token_usage(response) == usage
    assert fake.usage_calls == [response]


def test_get_token_usage_zero_fills_once_the_queue_drains():
    fake = FakeLlmClient(usages=[TokenUsage(1000, 600)])

    assert fake.get_token_usage(object()) == TokenUsage(1000, 600)
    assert fake.get_token_usage(object()) == TokenUsage()


def test_enqueue_usage_appends_to_the_scripted_queue():
    fake = FakeLlmClient()
    fake.enqueue_usage(TokenUsage(10, 4))

    assert fake.get_token_usage(object()) == TokenUsage(10, 4)


def test_get_completion_returns_a_usable_response():
    fake = FakeLlmClient(completion_content="# Mock Plan\n")

    response = fake.get_completion([{"role": "user", "content": "hi"}], model="m")

    assert response.choices[0].message.content == "# Mock Plan\n"
    assert response.model == "fake-model"
    assert fake.completion_calls[0]["model"] == "m"


def test_fake_satisfies_the_llm_port():
    from teddy_executor.core.ports.outbound import ILlmClient

    assert isinstance(FakeLlmClient(), ILlmClient)


def test_fake_llm_client_fixture_registers_in_container(container, fake_llm_client):
    from teddy_executor.core.ports.outbound import ILlmClient

    assert container.resolve(ILlmClient) is fake_llm_client
