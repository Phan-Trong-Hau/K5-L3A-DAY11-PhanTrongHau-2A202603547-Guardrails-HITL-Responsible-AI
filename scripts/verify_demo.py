#!/usr/bin/env python3
"""Run offline demo/history checks, without making provider calls."""
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    raise SystemExit(subprocess.call(
        [sys.executable, '-m', 'pytest', 'tests/demo', '-q'], cwd=root))
