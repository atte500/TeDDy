import os
from unittest.mock import MagicMock
from teddy_executor.core.services.context_service import ContextService
from teddy_executor.adapters.outbound.local_file_system_adapter import LocalFileSystemAdapter
from teddy_executor.core.services.edit_simulator import EditSimulator

def test_repro():
    # Setup
    root = "debug/repro_root"
    os.makedirs(root, exist_ok=True)
    
    # Create a spec file with a very long line
    long_content = "This is a very long line that will definitely exceed the maximum file name length allowed by the operating system when treated as a path. " * 20
    spec_path = "long_spec.md"
    with open(os.path.join(root, spec_path), "w") as f:
        f.write(long_content)

    # Initialize components
    fs_adapter = LocalFileSystemAdapter(EditSimulator(), root_dir=root)
    repo_gen = MagicMock()
    repo_gen.generate_tree.return_value = "tree"
    env_insp = MagicMock()
    env_insp.get_environment_info.return_value = {}
    env_insp.get_git_status.return_value = ""
    llm_client = MagicMock()
    llm_client.get_text_token_count.return_value = 10

    service = ContextService(fs_adapter, repo_gen, env_insp, llm_client)

    print("Attempting to gather context with long spec file...")
    try:
        # This should now succeed after the fix
        result = service.get_context(context_files={"Default": [spec_path]})
        print("SUCCESS: Context gathering succeeded.")
        # Verify content was read correctly
        if result.items and spec_path in result.items[0].path:
             print(f"VERIFIED: Correctly resolved {result.items[0].path}")
    except Exception as e:
        print(f"FAILURE: System crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_repro()