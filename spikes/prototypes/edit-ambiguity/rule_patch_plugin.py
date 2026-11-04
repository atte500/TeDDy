"""pytest plugin: run the existing suite under the proposed refined rule.

Load with:
    PYTHONPATH=spikes/prototypes/edit-ambiguity uv run pytest -p rule_patch_plugin <targets>
"""

from rule_harness import install_refined_rule

install_refined_rule()
