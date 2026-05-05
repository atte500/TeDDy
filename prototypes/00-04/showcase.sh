#!/bin/bash
# Re-install dependencies if needed, then run the isolated prototype runner
export PYTHONPATH=$PYTHONPATH:$(pwd)
poetry run python prototypes/00-04/runner.py