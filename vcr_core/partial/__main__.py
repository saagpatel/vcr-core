"""Validate cassette files or count bundled fixtures."""

import argparse
import sys
from pathlib import Path

from . import iter_fixtures, load


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate files or directories recursively")
    validate.add_argument("paths", nargs="+", type=Path)
    commands.add_parser("count", help="count bundled fixtures by class")
    args = parser.parse_args()
    if args.command == "count":
        counts = dict.fromkeys(("split_codepoint", "partial_event", "early_close"), 0)
        for cassette in iter_fixtures():
            counts[cassette.cls] += 1
        print(
            " ".join(f"{kind}={count}" for kind, count in counts.items()),
            f"total={sum(counts.values())}",
        )
        return 0
    failed = False
    for path in args.paths:
        paths = sorted(path.glob("**/*.pcas.json")) if path.is_dir() else [path]
        for candidate in paths:
            try:
                load(candidate)
            except (OSError, ValueError) as exc:
                print(f"{candidate}: {exc}", file=sys.stderr)
                failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
