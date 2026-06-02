import os
import time
import pytest
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.repo_tree_generator import IRepoTreeGenerator
from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.web_scraper import WebScraper as IWebScraper
from teddy_executor.core.services.context_service import ContextService
from tests.harness.setup.mocking import register_mock


@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true",
    reason="Performance tests are flaky on CI runners due to environment variance",
)
def test_context_gathering_is_performant_for_large_repos(container):
    # Setup mocks
    fs = register_mock(container, IFileSystemManager)
    # Use standard list comprehension for path metadata mocks
    paths = [f"file_{i}.py" for i in range(500)]
    fs.get_context_paths.return_value = paths
    fs.resolve_paths_from_files.side_effect = lambda x: x
    fs.read_files_in_vault.return_value = {p: "some content " * 10 for p in paths}

    tree = register_mock(container, IRepoTreeGenerator)
    tree.generate_tree.return_value = "tree"

    env = register_mock(container, IEnvironmentInspector)
    env.get_environment_info.return_value = {}
    env.get_git_status.return_value = ""

    llm = register_mock(container, ILlmClient)

    # Simulate a slow adapter (6ms per call as observed in profiling)
    def slow_count(text, model=None):
        time.sleep(0.006)
        return len(text)

    llm.get_text_token_count.side_effect = slow_count

    scraper = register_mock(container, IWebScraper)

    service = ContextService(fs, tree, env, llm, scraper)

    # 500 files * 0.006s = 3s synchronous.
    # With parallelization on a modern machine, it should be well under 1s.
    start = time.perf_counter()
    service.get_context()
    end = time.perf_counter()

    duration = end - start
    print(f"Gathering context for 500 files took {duration:.4f}s")

    assert duration < 1.0, f"Context gathering is too slow: {duration:.4f}s"


if __name__ == "__main__":
    test_context_gathering_is_performant_for_large_repos()
