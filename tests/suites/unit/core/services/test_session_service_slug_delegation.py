from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository


def test_resolve_session_from_slug_delegates_to_repository(env):
    # Arrange: the repository is the collaborator whose slug lookup must be reused.
    repository = env.mock_port(ISessionRepository)
    repository.resolve_session_from_slug.return_value = "20260124_153000-add-user-auth"
    service = env.get_service(ISessionManager)

    # Act
    resolved = service.resolve_session_from_slug("add-user-auth")

    # Assert: the service forwards the slug verbatim and returns the repository's answer.
    repository.resolve_session_from_slug.assert_called_once_with("add-user-auth")
    assert resolved == "20260124_153000-add-user-auth"
