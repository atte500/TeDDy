#!/bin/bash
#
# This script serves as a verifiable guide to the solution for the mypy pre-commit error.
# The root cause is that the mypy hook needs `types-PyYAML` in its own isolated environment.

echo "SOLUTION: Modify .pre-commit-config.yaml"
echo "------------------------------------------"
echo "The 'mypy' hook definition needs to be updated from:"
echo "
-   repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
    -   id: mypy
"
echo "to:"
echo "
-   repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
    -   id: mypy
        additional_dependencies: [\"types-PyYAML\"] # <-- This line is the fix
"
echo "------------------------------------------"
echo "VERIFICATION STEP:"
echo "After applying the change above to the root .pre-commit-config.yaml file,"
echo "run the following command. It should now pass."
echo ""
echo "poetry run pre-commit run mypy --all-files"
echo ""
echo "Solution verification guide created."
