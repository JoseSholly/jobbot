"""`uv run jobbot-build-profile`: CV PDF -> profile.

Modes:
  --chat-id N                 download the CV that user sent the bot, save to DB, DM them
  --pdf cv.pdf --out p.json   local only: write a hand-editable profile.json (no DB)
  --pdf cv.pdf --chat-id N    parse a local PDF and save it as user N's profile in the DB
  --all                       re-parse every user's stored CV (after parser upgrades)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from jobbot.adapters.pdf import pdf_to_text
from jobbot.config import load_settings
from jobbot.container import Container
from jobbot.logging_setup import setup_logging
from jobbot.services.profile import ProfileBuildError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--chat-id", type=int)
    p.add_argument("--pdf", type=Path)
    p.add_argument("--out", type=Path, help="write profile JSON here (local mode)")
    p.add_argument(
        "--all",
        action="store_true",
        help="re-parse every user's stored CV with the current parser and DM them",
    )
    p.add_argument("--config", type=Path)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    if not args.chat_id and not args.pdf and not args.all:
        p.error("give --chat-id and/or --pdf, or --all")
    return args


async def run(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    local_only = args.pdf is not None and args.chat_id is None
    async with Container(settings) as container:
        if local_only:
            from jobbot.services.profile import ProfileService

            service = ProfileService(profiles=None, llm=container.llm())  # type: ignore[arg-type]
            profile = await service.parse(pdf_to_text(args.pdf.read_bytes()))
            text = json.dumps(profile.to_dict(), indent=2, ensure_ascii=False)
            if args.out:
                args.out.write_text(text + "\n")
                print(f"wrote {args.out}; review and edit it by hand")
            else:
                print(text)
            return 0

        service = container.profile_service()
        if args.all:
            results = await service.rebuild_all()
            print(json.dumps({str(k): v for k, v in results.items()}, indent=2))
            return 0 if all(v == "ok" for v in results.values()) else 1
        try:
            if args.pdf:
                profile = await service.build_from_text(args.chat_id, pdf_to_text(args.pdf.read_bytes()))
            else:
                profile = await service.build_from_upload(args.chat_id)
        except ProfileBuildError as exc:
            print(f"profile build failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    setup_logging(args.verbose)
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
