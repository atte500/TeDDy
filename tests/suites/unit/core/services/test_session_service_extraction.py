from teddy_executor.core.ports.outbound.session_manager import ISessionManager


def test_extract_resource_path_normalizes_slashes(env):
    """
    Scenario: The AI provides paths with backslashes (Windows style)
    either in Markdown links or raw strings. SessionService must
    normalize these to forward slashes.
    """
    # Arrange
    service = env.get_service(ISessionManager)

    # Act / Assert
    # 1. Standard forward slash link
    assert service._extract_resource_path("[file](src/logic.py)") == "src/logic.py"

    # 2. Windows backslash link
    assert service._extract_resource_path("[file](src\\logic.py)") == "src/logic.py"

    # 3. Raw Windows path
    assert service._extract_resource_path("docs\\spec.md") == "docs/spec.md"

    # 4. Mixed slashes and leading slash
    assert (
        service._extract_resource_path("[file](\\src/mixed\\path.py)")
        == "src/mixed/path.py"
    )
