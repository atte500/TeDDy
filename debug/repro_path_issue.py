import os
from pathlib import Path
from teddy_executor.adapters.outbound.local_repo_tree_generator import LocalRepoTreeGenerator

def test_repro():
    tmp_path = Path("debug/tmp_test_tree").absolute()
    tmp_path.mkdir(parents=True, exist_ok=True)
    
    # Create deep structure
    deep_dir = tmp_path / "a" / "b" / "c"
    deep_dir.mkdir(parents=True, exist_ok=True)
    (deep_dir / "file.txt").touch()
    
    generator = LocalRepoTreeGenerator(str(tmp_path))
    tree_output = generator.generate_tree()
    
    print("Tree Output:")
    print(tree_output)
    
    # On Windows, this is expected to contain backslashes which causes the CI failure.
    # We want it to ALWAYS contain forward slashes for protocol consistency.
    if "\\" in tree_output:
        print("FAILURE: Backslashes found in tree output!")
    else:
        print("SUCCESS: No backslashes found.")

    if "./a/b:" not in tree_output:
        print("FAILURE: Expected section './a/b:' not found.")
    else:
        print("SUCCESS: Section './a/b:' found.")

if __name__ == "__main__":
    try:
        test_repro()
    finally:
        import shutil
        if os.path.exists("debug/tmp_test_tree"):
            shutil.rmtree("debug/tmp_test_tree")