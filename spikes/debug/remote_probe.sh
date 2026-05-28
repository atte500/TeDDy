#!/bin/bash
# Probe to verify if increasing timeout prevents the Windows worker crash.
# We run ONLY the failing test with a 60s timeout.

echo "Running probe on $(uname -a)"
poetry run pytest tests/suites/unit/adapters/inbound/test_reviewer_widgets.py::test_detail_item_contains_label_for_wrapping -v --timeout=60