"""Print a report to stdout; diagnostics contain reason codes, never message text."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .audit import InputError, audit_stream


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline checks of one Technocore room's exported JSONL.")
    parser.add_argument("input", help="Path to a raw JSONL export, or - for binary stdin")
    parser.add_argument("--room", required=True, help="Exact room the messages were signed for")
    parser.add_argument("--expected-did", help="Require every record to be signed by this independently obtained DID")
    parser.add_argument("--expected-sha256", help="Compare raw file bytes against an independently obtained commitment")
    parser.add_argument("--allow-unsigned", action="store_true", help="Allow unsigned records if all other checks pass")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    options = dict(room=args.room, expected_did=args.expected_did, expected_sha256=args.expected_sha256,
                   allow_unsigned=args.allow_unsigned)
    try:
        if args.input == "-":
            report = audit_stream(sys.stdin.buffer, **options)
        else:
            with Path(args.input).open("rb") as stream:
                report = audit_stream(stream, **options)
    except InputError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    except OSError:
        print(json.dumps({"error": "input_io_error"}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False))
    return 0 if report["status"] == "passed" else 1
