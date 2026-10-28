import argparse
import sys
from pathlib import Path

from . import config, pipeline


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="hazard", description="Innlandet hazard digest harness")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="fetch -> normalize -> draft -> validate (stops at the human gate)")
    r.add_argument("--backend", choices=["template", "claude"], default="template")
    r.add_argument("--source-dir", type=Path, help="use saved raw payloads instead of the live API")
    a = sub.add_parser("approve", help="human gate: publish a validated run")
    a.add_argument("run_dir", type=Path)
    sub.add_parser("status", help="show kill-switch state and failure streak")
    args = p.parse_args(argv)
    try:
        if args.cmd == "run":
            d = pipeline.run(args.backend, args.source_dir)
            print(f"OK  {d}\n    review {d / 'digest.md'} then: python -m hazard approve {d}")
        elif args.cmd == "approve":
            print(f"PUBLISHED {pipeline.approve(args.run_dir)}")
        else:
            state = "ENGAGED" if config.KILL_FILE.exists() else "off"
            print("kill switch:", state, "| failure streak:", pipeline._streak())
    except pipeline.Halted as e:
        print(f"HALTED: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
