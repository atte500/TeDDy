#!/bin/bash
set -e

echo "##[group]remote_probe"
echo "--- System Memory Info ---"
free -m

echo ""
echo "--- Attempting to allocate 6GB RAM ---"
# Use python to safely allocate memory and hold it
python3 -c "
import time
try:
    data = bytearray(6 * 1024 * 1024 * 1024)
    print('Successfully allocated 6GB')
    time.sleep(5)
except MemoryError:
    print('Failed to allocate 6GB: MemoryError')
except Exception as e:
    print(f'Failed with error: {e}')
" || echo "Process exited with code $?"

echo ""
echo "--- Final Memory State ---"
free -m
echo "##[endgroup]"