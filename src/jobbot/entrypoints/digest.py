"""`uv run jobbot-digest`: send the morning/evening digest to every active user."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jobbot.config import load_settings
from jobbot.container import Container
from jobbot.domain.models import Profile, Slot
from jobbot.logging_setup import setup_logging
from jobbot.services.digest import DigestOptions, slot_for


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--slot",
        choices=[s.value for s in Slot],
        help="morning/evening (default: inferred from the current WAT time)",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="print digests instead of sending; don't record anything"
    )
    p.add_argument("--user", type=int, help="only run for this chat_id")
    p.add_argument("--profile-file", type=Path, help="run without a database for a single local profile.json")
    p.add_argument("--sources", help="comma-separated subset of sources to use (e.g. remotive,jobicy)")
    p.add_argument("--no-reasons", action="store_true", help="skip Gemini match reasons")
    p.add_argument(
        "--once-per-slot",
        action="store_true",
        help="do nothing if this slot was already delivered today (for schedulers)",
    )
    p.add_argument("--config", type=Path, help="path to config.yaml")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    if args.no_reasons:
        settings.raw.setdefault("llm", {})["match_reasons"] = False
    tz = ZoneInfo(settings.digest.get("timezone", "Africa/Lagos"))
    now_local = datetime.now(tz)
    slot = Slot(args.slot) if args.slot else slot_for(now_local)
    start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    local_profile = None
    if args.profile_file:
        local_profile = Profile.from_dict(json.loads(args.profile_file.read_text()))
    elif not settings.secrets.database_url:
        print("DATABASE_URL is not set. Use --profile-file profile.json for a local run.", file=sys.stderr)
        return 2

    only = {s.strip() for s in args.sources.split(",")} if args.sources else None
    digest_cfg, llm_cfg, retention = settings.digest, settings.llm, settings.retention
    opts = DigestOptions(
        slot=slot,
        dry_run=args.dry_run,
        only_chat_id=args.user,
        max_keywords=int(settings.raw.get("search", {}).get("max_keywords", 12)),
        max_skills=int(settings.raw.get("search", {}).get("max_skills", 4)),
        max_age_days=int(digest_cfg.get("max_age_days", 14)),
        sent_retention_days=int(retention.get("sent_days", 60)),
        jobs_retention_days=int(retention.get("jobs_days", 90)),
        match_reasons=bool(llm_cfg.get("match_reasons", True)),
        max_reason_users=int(llm_cfg.get("max_reason_users_per_run", 50)),
        send_delay_seconds=float(digest_cfg.get("send_delay_seconds", 0.5)),
        once_per_slot_since=start_of_day if args.once_per_slot else None,
    )

    async with Container(
        settings, dry_run=args.dry_run, local_profile=local_profile, only_sources=only
    ) as container:
        service = container.digest_service()
        report = await service.run(opts)
        if args.dry_run:
            notifier = container.notifier()
            for chat_id, messages in report.previews.items():
                for message in messages:
                    await notifier.send(chat_id, message)
    if report.skipped_reason:
        print(f"skipped: {report.skipped_reason}")
        return 0
    print(json.dumps(report.as_stats(), indent=2))
    return 0 if not report.users_failed else 1


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    setup_logging(args.verbose)
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
