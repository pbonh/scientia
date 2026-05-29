"""Make the package and test helpers importable without an editable install.

Adds ``src/`` (so ``import scientia`` resolves to ``./src/scientia``) and the
repo root (so ``from tests... import ...`` resolves) to ``sys.path``.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
