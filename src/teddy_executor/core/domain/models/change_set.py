from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChangeSet:
    path: Path
    before_content: str
    after_content: str
    action_type: str  # 'CREATE' or 'EDIT'
