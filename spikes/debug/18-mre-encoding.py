import os
import platform
from pathlib import Path

def reproduce():
    print(f"OS: {platform.system()}")
    
    test_file = Path("spikes/debug/test_encoding.txt")
    content = "Status: 🟢"
    
    print("\nAttempting write simulating cp1252 (Windows default)...")
    try:
        # We explicitly use cp1252 to simulate the Windows crash on any OS
        test_file.write_text(content, encoding="cp1252")
        print("SUCCESS: Write passed (unexpected)")
    except UnicodeEncodeError as e:
        print(f"CAUGHT EXPECTED ERROR: {e}")

    print("\nAttempting write WITH encoding='utf-8' (The Fix)...")
    try:
        test_file.write_text(content, encoding="utf-8")
        read_back = test_file.read_text(encoding="utf-8")
        print(f"SUCCESS: Read back: {read_back}")
    except Exception as e:
        print(f"FAILURE: {e}")
    finally:
        if test_file.exists():
            test_file.unlink()

if __name__ == "__main__":
    reproduce()