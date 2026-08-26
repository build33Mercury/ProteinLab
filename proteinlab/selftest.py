from __future__ import annotations

import argparse
from pathlib import Path

from .validation import run_validation_suite


def main() -> int:
    parser = argparse.ArgumentParser(description="Protein Lab scientific/runtime self-test")
    parser.add_argument("--quick", action="store_true", help="Skip built-in structure checks")
    parser.add_argument("--no-runtime", action="store_true", help="Skip installed scientific dependency checks")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = run_validation_suite(root, include_runtime=not args.no_runtime, include_builtins=not args.quick)
    print(report.to_text())
    return 0 if report.all_required_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
