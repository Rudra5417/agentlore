#!/usr/bin/env python3
"""Run the rmem test suite.

    python3 run_tests.py

Equivalent to `python3 -m unittest discover -s tests -v`. Declared explicitly so the
repo has one obvious command, the same way the tool itself has no build step.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    sys.path.insert(0, str(ROOT / "tests"))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
