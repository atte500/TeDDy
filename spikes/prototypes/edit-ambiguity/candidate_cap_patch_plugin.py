"""pytest plugin: evaluate every seeded candidate instead of only the top five.

`_evaluate_candidates` reads `CANDIDATE_EVALUATION_CAP` as a module global at
call time, so rebinding it disables the refinement cap without copying any
matcher logic. This exposes whether the existing suite pins cap-dependent
behaviour before the slice removes the cap for an exact candidate count.

Load with:
    PYTHONPATH=spikes/prototypes/edit-ambiguity uv run pytest -p candidate_cap_patch_plugin <targets>
"""

import teddy_executor.core.services.validation_rules.edit_matcher as edit_matcher

edit_matcher.CANDIDATE_EVALUATION_CAP = 10**9
