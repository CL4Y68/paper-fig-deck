# -*- coding: utf-8 -*-
"""Make `import kit` / `import deck` work without installing the project."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
for p in (str(PIPELINE), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
