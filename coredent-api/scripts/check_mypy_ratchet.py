#!/usr/bin/env python3
"""mypy ratchet gate (L-2 FIX).

Runs mypy with the repo configuration and fails if the number of remaining
errors exceeds the committed baseline in scripts/mypy_baseline.txt. This
turns a 994-error legacy codebase into a monotonic improvement surface:
new code cannot add errors, and shrinking the baseline is a one-line PR.

Usage:
    python scripts/check_mypy_ratchet.py          # gate (CI)
    python scripts/check_mypy_ratchet.py --update # rewrite baseline
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "scripts" / "mypy_baseline.txt"


def current_error_count() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", "app", "--no-error-summary"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    # mypy exit 0 == clean; 1 == errors printed; 2 == fatal (return as-is).
    if proc.returncode not in (0, 1):
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)
    errors = [line for line in proc.stdout.splitlines() if ": error:" in line]
    return len(errors), proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()

    count, output = current_error_count()

    if args.update:
        BASELINE.write_text(f"{count}\n", encoding="utf-8")
        print(f"Baseline updated to {count} errors.")
        return 0

    if not BASELINE.exists():
        print(
            "No baseline found. Run 'python scripts/check_mypy_ratchet.py --update' "
            "once, commit scripts/mypy_baseline.txt, and re-run."
        )
        return 2

    baseline = int(BASELINE.read_text(encoding="utf-8").strip() or "0")
    if count > baseline:
        print(
            f"mypy ratchet FAILED: {count} errors > baseline {baseline}.\n"
            "Fix the new errors, or if they are pre-existing, run "
            "'python scripts/check_mypy_ratchet.py --update' and explain the "
            "increase in your PR."
        )
        print("\nFirst new errors (relative to baseline count):")
        for line in output.splitlines():
            if ": error:" in line:
                print("  " + line)
                if sum(1 for l in output.splitlines() if ": error:" in l) > 20:
                    break
        return 1

    print(f"mypy ratchet OK: {count} errors <= baseline {baseline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())