"""Put the skill's scripts/ directory on sys.path so tests can `import
apply_profile_models`. Also adds the sibling kanban-emit scripts/ dir
that apply_profile_models depends on.

Tests do `from tests import _paths  # noqa: F401` before importing.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_SCRIPTS = _HERE.parent.parent / "scripts"
_EMIT_SCRIPTS = (
    _HERE.parent.parent.parent / "scientia-kanban-emit" / "scripts"
)
for path in (_SCRIPTS, _EMIT_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
