import os

spike_file = "test_exclusive.txt"

# Clean up previous runs if necessary
if os.path.exists(spike_file):
    os.remove(spike_file)

try:
    # First attempt: This should succeed.
    print(f"Attempting to create '{spike_file}' for the first time...")
    with open(spike_file, "x") as f:
        f.write("Success!")
    print("File created successfully.")

    # Second attempt: This should fail.
    print(f"Attempting to create '{spike_file}' for the second time...")
    with open(spike_file, "x") as f:
        # This line should not be reached.
        f.write("This should not happen.")

except FileExistsError:
    print("Successfully caught FileExistsError as expected.")
    # Clean up the created file
    os.remove(spike_file)
    print("Spike successful: 'x' mode works as documented.")
    exit(0)
except Exception as e:
    print(f"Caught an unexpected exception: {type(e).__name__}: {e}")
    # Clean up if file was created
    if os.path.exists(spike_file):
        os.remove(spike_file)
    exit(1)

print("Spike failed: FileExistsError was not raised on the second attempt.")
# Clean up if file was created
if os.path.exists(spike_file):
    os.remove(spike_file)
exit(1)
