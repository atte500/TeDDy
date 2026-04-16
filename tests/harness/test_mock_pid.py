import os
from unittest.mock import MagicMock

try:
    pid = MagicMock()
    pgid = os.getpgid(pid)
    print(f"Success: {pgid}")
except Exception as e:
    print(f"Failed: {type(e).__name__} - {e}")
