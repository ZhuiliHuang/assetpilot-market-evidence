from __future__ import annotations

import argparse
from pathlib import Path

from market_evidence.analysis_recovery import recover_analysis_reference


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore the latest validated analysis as a current or stale reference."
    )
    parser.add_argument("--current-root", required=True, type=Path)
    parser.add_argument("--historical-root", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    changed = recover_analysis_reference(args.current_root, args.historical_root)
    print("analysis reference recovered" if changed else "analysis recovery not required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
