"""
Regression test for Bug #19: Session crashes after first turn due to model prefix loss.

Verifies that prompt_manager.update_meta() preserves the user-configured model
(including the openrouter/ prefix) and stores the actual serving model separately
in meta["actual_model"].
"""

import yaml
from teddy_executor.core.services.prompt_manager import PromptManager
from types import SimpleNamespace


class MockFileSystem:
    """Minimal IFileSystemManager mock for testing update_meta()."""

    def __init__(self):
        self.files = {}
        self.exists_cache = set()

    def path_exists(self, path):
        return path in self.exists_cache or path in self.files

    def read_file(self, path):
        return self.files.get(path, "")

    def write_file(self, path, content):
        self.files[path] = content


class MockResponse:
    """Simulates a Litellm response object with an actual serving model."""

    def __init__(self, actual_model="deepseek/deepseek-v4-flash-20260423"):
        self.model = actual_model
        choice = SimpleNamespace(
            finish_reason="stop", message=SimpleNamespace(content="Hello")
        )
        self.choices = [choice]


class TestBug19ModelPrefixPreservation:
    """Regression tests for Bug #19."""

    def setup_method(self):
        self.fs = MockFileSystem()
        self.mgr = PromptManager(file_system_manager=self.fs)

    def test_preserves_openrouter_prefix(self):
        """
        Verifies that update_meta() preserves the user-configured model
        with the openrouter/ prefix, and stores the actual model in actual_model.
        """
        original_model = "openrouter/deepseek/deepseek-v4-flash:nitro"
        meta = {
            "agent_name": "pathfinder",
            "model": original_model,
            "turn_cost": 0.0,
            "token_count": 0,
        }
        meta_file_path = "/tmp/test/01/meta.yaml"
        response = MockResponse(actual_model="deepseek/deepseek-v4-flash-20260423")

        self.mgr.update_meta(
            meta,
            response,
            token_count=100,
            turn_cost=0.001,
            meta_file_path=meta_file_path,
        )

        # The user-configured model MUST be preserved (with openrouter/ prefix)
        assert meta["model"] == original_model, (
            f"Expected meta['model'] to be '{original_model}', got '{meta['model']}'"
        )
        assert meta["model"].startswith("openrouter/"), "openrouter/ prefix was lost!"

        # The actual serving model MUST be stored in actual_model
        assert meta.get("actual_model") == "deepseek/deepseek-v4-flash-20260423", (
            f"Expected actual_model='deepseek/deepseek-v4-flash-20260423', "
            f"got '{meta.get('actual_model')}'"
        )

        # Verify that the model can still be used for routing in Turn 2
        model_for_turn2 = meta.get("model")
        assert model_for_turn2.startswith("openrouter/"), (
            "Model read for Turn 2 routing lost the openrouter/ prefix!"
        )

    def test_overwrites_model_when_not_previously_set(self):
        """
        Verifies that if meta["model"] was never set (e.g., first turn
        in a session with no override), the actual model is stored directly.
        """
        meta = {
            "agent_name": "pathfinder",
            "turn_cost": 0.0,
            "token_count": 0,
            # No "model" key set
        }
        meta_file_path = "/tmp/test/01/meta.yaml"
        response = MockResponse(actual_model="deepseek/deepseek-v4-flash-20260423")

        self.mgr.update_meta(
            meta,
            response,
            token_count=100,
            turn_cost=0.001,
            meta_file_path=meta_file_path,
        )

        assert meta.get("model") == "deepseek/deepseek-v4-flash-20260423"
        assert meta.get("actual_model") == "deepseek/deepseek-v4-flash-20260423"

    def test_preserve_meta_when_same_model(self):
        """
        Verifies that if the actual model matches the stored model, nothing changes.
        """
        original_model = "deepseek/deepseek-v4-flash-20260423"
        meta = {
            "agent_name": "pathfinder",
            "model": original_model,
            "turn_cost": 0.0,
            "token_count": 0,
        }
        meta_file_path = "/tmp/test/01/meta.yaml"
        response = MockResponse(actual_model="deepseek/deepseek-v4-flash-20260423")

        self.mgr.update_meta(
            meta,
            response,
            token_count=100,
            turn_cost=0.001,
            meta_file_path=meta_file_path,
        )

        assert meta["model"] == original_model
        assert meta["actual_model"] == original_model

    def test_meta_file_written_correctly(self):
        """
        Verifies that the meta.yaml file written to disk contains both model
        and actual_model fields, and that model retains the openrouter/ prefix.
        """
        original_model = "openrouter/deepseek/deepseek-v4-flash:nitro"
        meta = {
            "agent_name": "pathfinder",
            "model": original_model,
            "turn_cost": 0.0,
            "token_count": 0,
        }
        meta_file_path = "/tmp/test_persist/01/meta.yaml"
        response = MockResponse(actual_model="deepseek/deepseek-v4-flash-20260423")

        self.mgr.update_meta(
            meta,
            response,
            token_count=100,
            turn_cost=0.001,
            meta_file_path=meta_file_path,
        )

        written_content = self.fs.files.get(meta_file_path, "")
        assert written_content, "No content written to meta.yaml"

        parsed = yaml.safe_load(written_content)
        assert parsed is not None, "meta.yaml could not be parsed"

        assert parsed.get("model") == original_model, (
            f"Persisted model is '{parsed.get('model')}', expected '{original_model}'"
        )
        assert parsed.get("actual_model") == "deepseek/deepseek-v4-flash-20260423", (
            f"Persisted actual_model is '{parsed.get('actual_model')}', "
            f"expected 'deepseek/deepseek-v4-flash-20260423'"
        )

    def test_other_meta_fields_preserved(self):
        """
        Verifies that other meta fields (turn_cost, token_count, finish_reason)
        are still written correctly alongside the fix.
        """
        meta = {
            "agent_name": "pathfinder",
            "model": "openrouter/deepseek/deepseek-v4-flash:nitro",
            "turn_cost": 0.0,
            "token_count": 0,
        }
        meta_file_path = "/tmp/test_fields/01/meta.yaml"
        response = MockResponse(actual_model="deepseek/deepseek-v4-flash-20260423")

        self.mgr.update_meta(
            meta,
            response,
            token_count=50,
            turn_cost=0.005,
            meta_file_path=meta_file_path,
        )

        assert meta["turn_cost"] == 0.005
        assert meta["token_count"] == 50
        assert meta.get("finish_reason") == "stop"
