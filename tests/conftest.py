import sys
from pathlib import Path

# Add the project root directory to the Python path.
# This is necessary to ensure that `pytest` can correctly resolve imports
# when running tests from a specific file path, as it might not add the
# project root to `sys.path` by default in that scenario.
# We add it to the beginning of the list to ensure it's checked first.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
