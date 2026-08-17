"""Restore Paris datasets to the pre–multi-city baseline.

Rebuilds Open Data Paris traffic + OSM extension + air (petite couronne only,
no grande couronne grid).

Run from repo root:
  python preprocessing/restore_paris.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    steps = [
        [sys.executable, str(ROOT / "preprocessing" / "build_data.py"), "2026-07-29"],
        [sys.executable, str(ROOT / "preprocessing" / "extend_region.py")],
        [sys.executable, str(ROOT / "preprocessing" / "refresh_air.py"), "--petite-couronne"],
        [sys.executable, str(ROOT / "preprocessing" / "update_correlations.py")],
    ]
    for cmd in steps:
        print(f"\n>>> {' '.join(cmd)}")
        subprocess.run(cmd, cwd=ROOT, check=True)
    print("\nParis restore complete -> data/paris/")


if __name__ == "__main__":
    main()
