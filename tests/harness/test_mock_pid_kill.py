import os
import signal
from unittest.mock import MagicMock

try:
    pid = MagicMock()
    pgid = os.getpgid(pid)
    print(f"pgid: {pgid}")
    os.killpg(pgid, signal.SIGKILL)
    print("Kill succeeded!")
except Exception as e:
    print(f"Failed: {type(e).__name__} - {e}")
