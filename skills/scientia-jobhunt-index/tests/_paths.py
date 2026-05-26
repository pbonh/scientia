"""Put the skill's scripts/ directory on sys.path so tests can `import rebuild_index`.

Tests do `from tests import _paths  # noqa: F401` before the import.
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
