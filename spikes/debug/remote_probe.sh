#!/bin/bash
echo "Starting Remote Probe..."

# Disable xdist (-n 0) and run the test 10 times.
# We also print the timeout just in case.
for i in {1..10}; do
    echo "Run $i..."
    # --timeout=15 to override the 5s timeout, to see if it just needs more time
    poetry run pytest tests/suites/acceptance/test_session_resume_robustness.py::test_resume_auto_detects_latest_session -n 0 -vv -s --timeout=15 || {
        echo "Crash detected on run $i!"
        exit 1
    }
done

echo "Probe completed successfully."