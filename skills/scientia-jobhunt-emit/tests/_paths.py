"""Put this skill's scripts/ on sys.path, plus the sibling kanban-emit and
kanban-init scripts/ dirs that jobhunt_emit imports from.

Tests do `from tests import _paths  # noqa: F401` before importing.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_SKILLS = _HERE.parent.parent.parent  # …/skills/
for path in (
    _HERE.parent.parent / "scripts",
    _SKILLS / "scientia-kanban-emit" / "scripts",
    _SKILLS / "scientia-kanban-init" / "scripts",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
