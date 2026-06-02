from typing import Any
from teddy_executor.core.ports.outbound.web_scraper import WebScraper as IWebScraper
from teddy_executor.core.services.context_service import ContextService
from tests.harness.setup.mocking import register_mock


def test_resolve_files_to_paths_expands_directories_recursively(
    container,
    mock_fs: Any,
    mock_tree_gen: Any,
    mock_inspector: Any,
    mock_llm_client: Any,
):
    """
    Verifies that ContextService resolves directory paths into recursive file lists.
    """
    # Arrange
    mock_scraper = register_mock(container, IWebScraper)
    service = ContextService(
        file_system_manager=mock_fs,
        repo_tree_generator=mock_tree_gen,
        environment_inspector=mock_inspector,
        llm_client=mock_llm_client,
        web_scraper=mock_scraper,
    )

    # Setup FSM behavior:
    # "src/utils" is a directory.
    # "src/main.py" is a file.
    mock_fs.is_dir.side_effect = lambda p: p == "src/utils"
    mock_fs.list_directory_recursive.return_value = [
        "src/utils/file1.py",
        "src/utils/file2.py",
        "src/utils/sub/file3.py",
    ]

    files = ["src/main.py", "src/utils"]

    # Act
    resolved_paths = service._resolve_files_to_paths(files)

    # Assert
    # We expect "src/utils" to be expanded and "src/main.py" to remain as is.
    expected = [
        "src/main.py",
        "src/utils/file1.py",
        "src/utils/file2.py",
        "src/utils/sub/file3.py",
    ]
    assert resolved_paths == expected
    mock_fs.is_dir.assert_any_call("src/utils")
    mock_fs.list_directory_recursive.assert_called_once_with("src/utils")


def test_resolve_recursive_ignores_urls_for_directory_checks(
    container,
    mock_fs: Any,
    mock_tree_gen: Any,
    mock_inspector: Any,
    mock_llm_client: Any,
):
    """
    Ensures that URLs are added to paths without calling is_dir on the filesystem manager.
    """
    # Arrange
    mock_scraper = register_mock(container, IWebScraper)
    service = ContextService(
        file_system_manager=mock_fs,
        repo_tree_generator=mock_tree_gen,
        environment_inspector=mock_inspector,
        llm_client=mock_llm_client,
        web_scraper=mock_scraper,
    )

    url = "https://example.com/spec.md"
    paths: list[str] = []
    processed_manifests: set[str] = set()

    # Act
    service._resolve_recursive(url, paths, processed_manifests)

    # Assert
    assert url in paths
    # Crucially, is_dir should NOT be called for the URL
    for call in mock_fs.is_dir.call_args_list:
        args, _ = call
        assert args[0] != url, f"is_dir was incorrectly called with URL: {url}"
