"""User-facing commands. Never print packets, credentials or upstream bodies."""
import argparse
import json
from pathlib import Path
import sys

from . import operations, transport
from .storage import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture", help="Save before text, without editing the method")
    capture.add_argument("--unknown-before", action="store_true", help="Explicit recovery when the actual prior text was lost")
    capture.add_argument("paths", nargs="+")
    finalize = commands.add_parser("finalize", help="Freeze actual after text for an accepted change")
    finalize.add_argument("change_id")
    for field in ("reason", "expected-effect", "initiator"):
        finalize.add_argument("--" + field, required=True)
    send = commands.add_parser("send", help="Attempt bounded delivery of due packets")
    send.add_argument("--retry-held", metavar="CHANGE_ID")
    status = commands.add_parser("status", help="Show unfinished records, or one specific receipt")
    status.add_argument("change_id", nargs="?")
    discard = commands.add_parser("discard", help="Explicitly remove one unfinalized capture")
    discard.add_argument("change_id")
    args = parser.parse_args(argv)
    try:
        store = Store(args.project_root)
        if (args.command in {"status", "send"} and not getattr(args, "change_id", None)
                and not store.path.exists() and not store.path.is_symlink()):
            print(json.dumps({"records": []} if args.command == "status" else
                             {"attempted": 0, "delivered": 0, "pending": 0, "held": 0}))
            return 0
        with store.locked():
            if args.command == "capture":
                result = operations.capture(store, args.paths, unknown=args.unknown_before)
            elif args.command == "finalize":
                result = operations.finalize(store, args.change_id, reason=args.reason,
                                             expected_effect=args.expected_effect, initiator=args.initiator)
            elif args.command == "send":
                result = operations.send(store, retry_held=args.retry_held)
            elif args.command == "discard":
                store.discard(args.change_id)
                result = {"change_id": args.change_id, "status": "discarded_unfinalized_capture"}
            else:
                result = {"records": operations.status(store, args.change_id)}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except transport.DeliveryError as error:
        print(json.dumps({"error": error.code, "retryable": error.transient}), file=sys.stderr)
    except ValueError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
    except OSError:
        print(json.dumps({"error": "Local capture unavailable or in use; check permissions and unfinished records"}), file=sys.stderr)
    return 1
