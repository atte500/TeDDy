import sys
import os
import platform

def run_probe():
    print(f"--- [DEBUG] Starting Remote Probe ---")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    
    print("\n[DIAGNOSTIC: Path Integrity]")
    print(f"OS Path Separator: '{os.sep}'")
    print(f"Path List Separator: '{os.pathsep}'")
    
    print("\n[DIAGNOSTIC: Environment Case Sensitivity]")
    os.environ['TEDDY_TEST'] = 'lowercase'
    val = os.environ.get('teddy_test', 'NOT FOUND (Case Sensitive)')
    print(f"Environment 'teddy_test' result: {val}")

    print("\n--- [DEBUG] Probe Logic Executed Successfully ---")

if __name__ == "__main__":
    try:
        run_probe()
    except Exception as e:
        print(f"[ERROR] Probe failed: {e}")
        sys.exit(1)