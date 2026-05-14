#!/bin/bash
echo "Starting Remote Probe..."

# Enable xdist (-n 4) and run the entire file 10 times.
for i in {1..10}; do
    echo "Run $i..."
    poetry run pytest tests/suites/acceptance/test_session_resume_robustness.py -n 4 -vv --timeout=15 || {
        echo "Crash detected on run $i!"
        exit 1
    }
done

echo "Probe completed successfully."