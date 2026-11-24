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
    parser.add_argument("--no-color", action="store_true", help="never use colors")
    parser.add_argument(
        "--run",
        action="store_true",
        help="also run one H2 single point per software (submitted when a scheduler is set)",
    )
    parser.add_argument(
        "--workdir",
        default=None,
        help="parent directory of the --run calculations (default: current directory)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the check and return the exit code: 0 ok, 1 failure, 2 bad config."""
    args = parse_args(argv)
    try:
        report = check(path=args.config, run=args.run, workdir=args.workdir)
    except ConfigError as error:
        print(f"amac-check: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        color = sys.stdout.isatty() and not args.no_color
        print(report.render(color=color, title=f"AMAC installation check — {args.config}"))
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
