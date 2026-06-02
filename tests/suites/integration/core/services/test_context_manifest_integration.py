from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from tests.harness.setup.test_environment import TestEnvironment


def test_context_service_expands_directories_from_manifest(monkeypatch):
    # Arrange
    env = TestEnvironment(monkeypatch).setup().with_real_filesystem()

    # Create a directory structure
    core_dir = env.workspace / "src" / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "logic.py").write_text("print('logic')")
    (core_dir / "models.py").write_text("class Model: pass")
    (env.workspace / "README.md").write_text("# TeDDy")

    # Create a manifest file containing the directory
    (env.workspace / "my.context").write_text("src/core/\nREADME.md")

    # Act
    service = env.container.resolve(IGetContextUseCase)
    context = service.get_context(
        context_files={"Manual": ["my.context"]}, include_tokens=False
    )

    # Assert
    # We expect src/core/logic.py, src/core/models.py, and README.md
    paths = context.scoped_paths["Manual"]
    assert "src/core/logic.py" in paths
    assert "src/core/models.py" in paths
    assert "README.md" in paths
    assert "my.context" not in paths  # Manifests themselves should be resolved away
