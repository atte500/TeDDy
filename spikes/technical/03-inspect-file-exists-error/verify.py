import os
import sys

print("--- Inspecting Python's FileExistsError ---")

spike_file_path = "spike_file.txt"

# Ensure the file does not exist initially
if os.path.exists(spike_file_path):
    os.remove(spike_file_path)

# 1. Create a file
with open(spike_file_path, "w") as f:
    f.write("content")
print(f"Step 1: Successfully created '{spike_file_path}'")

# 2. Attempt to create it again with exclusive access ('x' mode) to trigger the error
print(f"Step 2: Attempting to re-create '{spike_file_path}' with 'x' mode...")
try:
    with open(spike_file_path, "x") as f:
        # This code should not be reached
        f.write("this should fail")
except FileExistsError as e:
    print("\n[SUCCESS] Caught FileExistsError as expected.")
    print("--- Analysis of the exception object 'e' ---")
    print(f"  repr(e): {repr(e)}")
    print(f"  str(e):  '{str(e)}'")
    print(f"  e.strerror: '{e.strerror}'")
    print(f"  e.filename: '{e.filename}'")
    print("---")

# 3. Clean up
finally:
    if os.path.exists(spike_file_path):
        os.remove(spike_file_path)
    print("\nStep 3: Cleanup complete.")

sys.exit(0)
