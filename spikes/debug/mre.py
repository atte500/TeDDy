import os
import sys

def reproduce():
    print("--- [DEBUG] Starting MRE ---")
    try:
        # Simulate a check that might fail in restricted environments
        random_bytes = os.urandom(32)
        print(f"--- [DEBUG] Successfully generated {len(random_bytes)} bytes ---")
    except Exception as e:
        print(f"--- [DEBUG] CAUGHT ERROR: {e} ---")
        sys.exit(1)
    print("--- [DEBUG] MRE Finished ---")

if __name__ == "__main__":
    reproduce()