from __future__ import annotations

import argparse
import json

from market_evidence.source_registry import audit_source_coverage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit locked public source coverage.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Validate configuration without contacting any remote source.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.offline:
        raise SystemExit("Only --offline is supported until adapter probes are implemented.")
    print(json.dumps(audit_source_coverage(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
