import urllib.request
import json


def test_openrouter_mock_fixture(openrouter_mock):
    # Act: openrouter_mock is a fixture that returns the base URL
    url = f"{openrouter_mock}/api/v1/models"
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
        status = response.getcode()

    # Assert
    assert status == 200
    assert "data" in data
    assert data["data"][0]["id"] == "deepseek/deepseek-v4-flash"


def test_openrouter_mock_catalog_carries_cache_pricing(openrouter_mock):
    # Act: the served catalog mirrors the in-memory OPENROUTER_MODELS_RESPONSE
    url = f"{openrouter_mock}/api/v1/models"
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
    models = {model["id"]: model for model in data["data"]}

    # Assert: the primary model carries string-typed cache-pricing keys so the
    # hydrator Logic tests can assert cache-rate propagation.
    deepseek_pricing = models["deepseek/deepseek-v4-flash"]["pricing"]
    assert deepseek_pricing.get("input_cache_read") == "0.0000001"
    assert deepseek_pricing.get("input_cache_write") == "0.00000125"

    # Assert: a second model deliberately omits cache keys so the hydrator
    # Logic tests can assert defensive omission.
    gemini_pricing = models["google/gemini-2.0-flash-001"]["pricing"]
    assert "input_cache_read" not in gemini_pricing
    assert "input_cache_write" not in gemini_pricing
