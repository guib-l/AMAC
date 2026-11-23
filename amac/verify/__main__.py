"""Command line of the AMAC installation check."""

from __future__ import annotations

import argparse
import json
import sys

from amac.utils.exception import ConfigError
from amac.verify import DEFAULT_PATH, check


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        prog="amac-check",
        description="Check that this machine can run AMAC.",
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=DEFAULT_PATH,
        help=f"AMAC configuration file (default: {DEFAULT_PATH})",
    )
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the check and return the exit code: 0 ok, 1 failure, 2 bad config."""
    args = parse_args(argv)
    try:
        report = check(path=args.config)
    except ConfigError as error:
        print(f"amac-check: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report.to_dict(), indent=2) if args.json else report.render())
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
