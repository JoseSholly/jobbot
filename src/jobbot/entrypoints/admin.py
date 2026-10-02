"""`uv run jobbot-admin`: bootstrap + admin tasks from your terminal.

jobbot-admin bootstrap            make ADMIN_CHAT_ID an active admin user
jobbot-admin invite [--uses N] [--days D]
jobbot-admin users
jobbot-admin approve|pause|block CHAT_ID
jobbot-admin send-test            send a test message to ADMIN_CHAT_ID
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from jobbot.config import load_settings
from jobbot.container import Container
from jobbot.domain.models import UserStatus
from jobbot.interfaces.notifier import OutgoingMessage
from jobbot.logging_setup import setup_logging


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bootstrap")
    inv = sub.add_parser("invite")
    inv.add_argument("--uses", type=int, default=1)
    inv.add_argument("--days", type=int, default=14)
    sub.add_parser("users")
    for name in ("approve", "pause", "block"):
        sub.add_parser(name).add_argument("chat_id", type=int)
    sub.add_parser("send-test")
    return p.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    settings = load_settings()
    admin_id = settings.secrets.admin_chat_id
    async with Container(settings) as container:
        if args.cmd == "send-test":
            if not admin_id:
                print("ADMIN_CHAT_ID is not set", file=sys.stderr)
                return 2
            await container.notifier().send(
                admin_id, OutgoingMessage(text="✅ <b>JobBot</b> can reach you. Setup looks good.")
            )
            print("sent")
            return 0

        users = container.user_service()
        if args.cmd == "bootstrap":
            if not admin_id:
                print("ADMIN_CHAT_ID is not set", file=sys.stderr)
                return 2
            users.ensure_admin(admin_id)
            print(f"admin {admin_id} is active")
        elif args.cmd == "invite":
            code = users.create_invite(admin_id or 0, max_uses=args.uses, days_valid=args.days)
            print(f"invite code: {code}  (users send: /join {code})")
        elif args.cmd == "users":
            for u in users.list_users():
                flag = " (admin)" if u.is_admin else ""
                print(f"{u.chat_id:>14}  {u.status.value:<8} @{u.username or '-'}{flag}")
        else:
            status = {"approve": UserStatus.ACTIVE, "pause": UserStatus.PAUSED, "block": UserStatus.BLOCKED}[
                args.cmd
            ]
            users.set_status(args.chat_id, status)
            print(f"{args.chat_id} -> {status.value}")
    return 0


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    setup_logging()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
