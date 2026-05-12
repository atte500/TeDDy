import pathlib
import functools
from pathlib import Path

# --- THE SYSTEMIC FIX (To be moved to tests/conftest.py) ---
def apply_systemic_encoding_fix():
    original_write_text = Path.write_text
    original_read_text = Path.read_text

    @functools.wraps(original_write_text)
    def utf8_write_text(self, data, encoding=None, errors=None, newline=None):
        if encoding is None:
            encoding = "utf-8"
        return original_write_text(self, data, encoding=encoding, errors=errors, newline=newline)

    @functools.wraps(original_read_text)
    def utf8_read_text(self, encoding=None, errors=None):
        if encoding is None:
            encoding = "utf-8"
        return original_read_text(self, encoding=encoding, errors=errors)

    Path.write_text = utf8_write_text
    Path.read_text = utf8_read_text
    print("[SYSTEMIC FIX] Path.write_text and Path.read_text now default to UTF-8.")

# --- THE REPRODUCTION ---
def test_simulation():
    test_file = Path("spikes/debug/systemic_test.txt")
    content = "Status: 🟢"
    
    print("\n[Step 1] Attempting write WITHOUT fix (Simulating cp1252)...")
    try:
        # Simulate cp1252 failure
        test_file.write_text(content, encoding="cp1252")
    except UnicodeEncodeError as e:
        print(f"CAUGHT EXPECTED ERROR: {e}")

    print("\n[Step 2] Applying Systemic Fix...")
    apply_systemic_encoding_fix()

    print("\n[Step 3] Attempting SAME write call (encoding=None)...")
    try:
        # This call is identical to the one in Step 1 (or the failing test)
        test_file.write_text(content) 
        read_back = test_file.read_text()
        print(f"SUCCESS: Read back: {read_back}")
    except Exception as e:
        print(f"FAILURE: {e}")
    finally:
        if test_file.exists():
            test_file.unlink()

if __name__ == "__main__":
    test_simulation()