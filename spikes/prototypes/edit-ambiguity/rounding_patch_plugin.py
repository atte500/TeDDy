"""pytest plugin: return raw ratios instead of two-decimal scores.

`find_best_match` resolves `round` through its module globals, so rebinding that
name in the module disables the rounding without copying any matcher logic.

Load with:
    PYTHONPATH=spikes/prototypes/edit-ambiguity uv run pytest -p rounding_patch_plugin <targets>
"""

import teddy_executor.core.services.validation_rules.edit_matcher as edit_matcher

edit_matcher.round = lambda value, ndigits=None: value
