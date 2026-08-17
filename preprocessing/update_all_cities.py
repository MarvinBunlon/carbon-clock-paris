"""Update Lyon and Marseille only — Paris data is never modified here.

Run from repo root:
  python preprocessing/update_all_cities.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    py = sys.executable
    pre = ROOT / "preprocessing"
    # Paris: do not touch — use data/paris/ from GitHub + extend_region.py manually.
    run([py, str(pre / "build_city.py"), "lyon"])
    run([py, str(pre / "build_city.py"), "marseille"])
    print("\nLyon + Marseille updated. Paris unchanged.")


if __name__ == "__main__":
    main()
