"""Command line entry point: `python main.py [--small|--full] [command]`."""
from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional

from quanta import __version__
from quanta.cli.jobs import JOBS, run_jobs, summary_table
from quanta.config import PRESETS, build_settings
from quanta.io.csvio import describe_columns, read_table
from quanta.io.jsonio import diff_reports, load_report, save_report
from quanta.io.report import format_table

log = logging.getLogger("quanta")


def _common() -> argparse.ArgumentParser:
    """Options accepted both before and after the sub-command (SUPPRESS keeps the first value given)."""
    p = argparse.ArgumentParser(add_help=False)
    size = p.add_mutually_exclusive_group()
    size.add_argument("--small", dest="scale", action="store_const", const="small", default=argparse.SUPPRESS,
                      help="the default workload (about half a minute)")
    size.add_argument("--full", dest="scale", action="store_const", const="full", default=argparse.SUPPRESS,
                      help="roughly three times the work")
    size.add_argument("--tiny", dest="scale", action="store_const", const="tiny", default=argparse.SUPPRESS,
                      help="smoke-test workload used by the unit tests")
    p.add_argument("--seed", type=int, default=argparse.SUPPRESS, help="workload seed (default 2024)")
    p.add_argument("--config", default=argparse.SUPPRESS, metavar="FILE", help="INI file with a [scale] section")
    p.add_argument("--set", action="append", default=argparse.SUPPRESS, metavar="KEY=N",
                   help="override one scale parameter, e.g. --set queens_n=8")
    p.add_argument("--json", default=argparse.SUPPRESS, metavar="PATH", help="also write the report as JSON")
    p.add_argument("--numpy", action="store_true", default=argparse.SUPPRESS, help="use the optional NumPy paths")
    p.add_argument("-v", "--verbose", action="store_true", default=argparse.SUPPRESS, help="log progress to stderr")
    return p


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quanta", parents=[_common()],
                                     description="Quanta: analytics and simulation toolkit.")
    parser.add_argument("--version", action="version", version="quanta " + __version__)
    parser.set_defaults(scale="small", seed=None, config=None, set=None, json=None, numpy=False, verbose=False)
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.add_parser("suite", parents=[_common()], help="run every job (the default)")
    for name, job in JOBS.items():
        sub.add_parser(name, parents=[_common()], help=(job.__doc__ or "").strip().splitlines()[0])
    sub.add_parser("list", parents=[_common()], help="list the available jobs and scale presets")
    desc = sub.add_parser("describe", parents=[_common()], help="summarise the columns of a CSV file")
    desc.add_argument("path")
    cmp_ = sub.add_parser("compare", parents=[_common()], help="show the differences between two JSON reports")
    cmp_.add_argument("old")
    cmp_.add_argument("new")
    return parser


def _cmd_list() -> int:
    print(format_table(["job", "what it does"], [[n, (j.__doc__ or "").strip().splitlines()[0]] for n, j in JOBS.items()]))
    print()
    print("scales: " + ", ".join(sorted(PRESETS)))
    return 0


def _cmd_describe(path: str) -> int:
    table = read_table(path)
    print("%s: %d rows, %d columns" % (path, len(table), len(table.columns)))
    for name, kind in describe_columns(table).items():
        print("  %-12s %s" % (name, kind))
    return 0


def _cmd_compare(old: str, new: str) -> int:
    changes = diff_reports(load_report(old), load_report(new))
    if not changes:
        print("reports are identical")
        return 0
    for key, change in changes.items():
        print("%s: %s" % (key, change))
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    command = args.command or "suite"
    try:
        if command == "list":
            return _cmd_list()
        if command == "describe":
            return _cmd_describe(args.path)
        if command == "compare":
            return _cmd_compare(args.old, args.new)
        cfg = build_settings(args.scale, args.config, args.set, args.seed, args.verbose, args.numpy)
    except (OSError, ValueError) as exc:
        print("quanta: error: %s" % exc, file=sys.stderr)
        return 2
    names = list(JOBS) if command == "suite" else [command]
    rep = run_jobs(cfg, names)
    print(rep.render())
    print()
    print(summary_table(rep))
    if args.json:
        save_report(args.json, rep.data)
    return 0
