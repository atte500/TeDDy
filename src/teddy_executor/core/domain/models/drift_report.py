"""Domain model describing drift between user files and bundled defaults.

Seam Items 3/4 (session-behaviour): ``InitService.check_drift`` returns this
immutable report so the CLI preflight can advise ``teddy init prompts`` /
``teddy init templates`` when the user's local copies have diverged from (or are
missing relative to) the bundled defaults.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DriftReport:
    """Immutable summary of user files that diverge from bundled defaults.

    Each field holds the *basenames* (e.g. ``pathfinder.xml``) of the affected
    files, preserving the canonical manifest order for deterministic output.
    """

    edited_prompts: tuple[str, ...] = ()
    missing_prompts: tuple[str, ...] = ()
    edited_templates: tuple[str, ...] = ()
    missing_templates: tuple[str, ...] = ()

    @property
    def prompts_drifted(self) -> bool:
        """True when any user prompt is edited or missing."""
        return bool(self.edited_prompts or self.missing_prompts)

    @property
    def templates_drifted(self) -> bool:
        """True when any user template is edited or missing."""
        return bool(self.edited_templates or self.missing_templates)

    @property
    def has_drift(self) -> bool:
        """True when any user prompt or template has drifted from its default."""
        return self.prompts_drifted or self.templates_drifted
