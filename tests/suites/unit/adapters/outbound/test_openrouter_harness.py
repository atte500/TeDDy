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
