#!/usr/bin/env python3
"""Run the rmem test suite.

    python3 run_tests.py

Equivalent to `python3 -m unittest discover -s tests -v`. Declared explicitly so the
repo has one obvious command, the same way the tool itself has no build step.

A failure is written to .test-failures/<utc-stamp>.log with the failing test names, the
Python version, the hash seed and the full output. This suite failed twice at random and
both times the evidence was thrown away by `run_tests.py | tail -3`, which turned a
five-minute fix into an afternoon of hunting. Capturing costs nothing when it passes.
"""

from __future__ import annotations

import datetime
import hashlib
import io
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class _Tee:
    """Write to the terminal and to a buffer, so a pipe cannot destroy the evidence."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def main():
    sys.path.insert(0, str(ROOT / "tests"))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    buffer = io.StringIO()
    result = unittest.TextTestRunner(verbosity=2, stream=_Tee(sys.stdout, buffer)).run(suite)

    if result.wasSuccessful():
        return 0

    names = [case.id() for case, _ in result.failures + result.errors]
    out_dir = ROOT / ".test-failures"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / ("%s.log" % datetime.datetime.now(datetime.timezone.utc)
                      .strftime("%Y%m%dT%H%M%SZ"))
    path.write_text(
        "cmd            : %s\n"
        "python         : %s\n"
        "PYTHONHASHSEED : %s\n"
        "platform       : %s\n"
        "rmem sha256[:16]: %s\n"
        "failing        : %s\n\n%s" % (
            " ".join(sys.argv),
            sys.version.split()[0],
            os.environ.get("PYTHONHASHSEED", "(unset)"),
            sys.platform,
            hashlib.sha256((ROOT / "rmem").read_bytes()).hexdigest()[:16],
            "\n                 ".join(names),
            buffer.getvalue()))
    print("\nFAILING: %s" % ", ".join(names))
    print("full output kept at %s" % path)
    return 1


if __name__ == "__main__":
    sys.exit(main())
