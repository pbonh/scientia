"""Make the bundle importable when running the suite without `pip install -e .`.

Adds the bundle root (this file's directory) to ``sys.path`` so ``import
kg_pipeline`` resolves to ``./kg_pipeline``.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
