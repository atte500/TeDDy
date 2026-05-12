import sys
import os
import platform

def run_probe():
    print(f"--- [DEBUG] Starting Remote Probe ---")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print(f"CWD: {os.getcwd()}")
    
    # Add diagnostic logic here...
    print("--- [DEBUG] Probe Logic Executed Successfully ---")

if __name__ == "__main__":
    try:
        run_probe()
    except Exception as e:
        print(f"[ERROR] Probe failed: {e}")
        sys.exit(1)