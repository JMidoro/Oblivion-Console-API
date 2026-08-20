from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

from oblivion_bridge.mailbox import atomic_write_json, read_json
from oblivion_bridge.models import MailboxRequest, MailboxResponse
from oblivion_bridge.settings import DEFAULT_MAILBOX_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit one manual Phase 1 mailbox command and print its response."
    )
    parser.add_argument("command", help="Raw Oblivion console command")
    parser.add_argument(
        "--mailbox-dir",
        type=Path,
        default=DEFAULT_MAILBOX_DIR,
        help=f"Mailbox directory (default: {DEFAULT_MAILBOX_DIR})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60,
        help="Seconds to wait for response.json (default: 60)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mailbox_dir: Path = args.mailbox_dir
    request_path = mailbox_dir / "request.json"
    response_path = mailbox_dir / "response.json"
    mailbox_dir.mkdir(parents=True, exist_ok=True)

    if request_path.exists() or response_path.exists():
        print(
            "Mailbox is not empty. Inspect request.json/response.json before retrying."
        )
        return 2

    request = MailboxRequest(
        request_id=str(uuid4()),
        commands=[args.command],
    )
    atomic_write_json(request_path, request.model_dump(mode="json"))

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        if response_path.exists():
            raw_response = read_json(response_path)
            response = MailboxResponse.model_validate(raw_response)
            if response.request_id != request.request_id:
                print("Ignoring response.json for another request ID.")
                time.sleep(0.05)
                continue

            print(
                json.dumps(
                    response.model_dump(mode="json"),
                    indent=2,
                    ensure_ascii=False,
                )
            )
            response_path.unlink(missing_ok=True)
            return 0

        time.sleep(0.05)

    print(f"Timed out after {args.timeout:g} seconds.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
