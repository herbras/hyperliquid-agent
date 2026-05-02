#!/usr/bin/env python3
"""
fetch_telegram_feed.py — pull latest messages dari Telegram channel via Telethon.

Default: @marketfeed (https://t.me/marketfeed) — market news/fundamentals.

Setup workflow (sekali):
  1. Get api_id + api_hash di https://my.telegram.org/apps
  2. Set di .env (atau ~/.hermes/.env):
       TELEGRAM_API_ID=12345678
       TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
       TELEGRAM_SESSION_PATH=~/.hermes/state/telegram.session   # optional
  3. First run interactive (paste phone + SMS code):
       python3 fetch_telegram_feed.py --setup
  4. Subsequent runs auto-baca session, no auth needed.

Usage:
  python3 fetch_telegram_feed.py                              # default marketfeed, 10 latest
  python3 fetch_telegram_feed.py --channel marketfeed --limit 20
  python3 fetch_telegram_feed.py --hours 4                    # cuma 4 jam terakhir
  python3 fetch_telegram_feed.py --channel cryptobubbles --hours 2
  python3 fetch_telegram_feed.py --output ~/.hermes/state/telegram-feed.json

Output: JSON {channel, fetched_at, count, messages: [{id, date, text, views, urls}]}
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from telethon import TelegramClient
except ImportError:
    print("ERROR: pip install --user --break-system-packages telethon", file=sys.stderr)
    sys.exit(1)


API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION = os.path.expanduser(
    os.environ.get("TELEGRAM_SESSION_PATH", "~/.hermes/state/telegram.session")
)


def extract_urls(text):
    """Extract URLs dari raw text (regex sederhana)."""
    if not text:
        return []
    return re.findall(r"https?://[^\s\)\]\}]+", text)


async def fetch_messages(channel, limit, hours_filter=None):
    if not API_ID or not API_HASH:
        print("ERROR: TELEGRAM_API_ID + TELEGRAM_API_HASH wajib di-set", file=sys.stderr)
        print("Get di: https://my.telegram.org/apps", file=sys.stderr)
        sys.exit(2)

    Path(SESSION).parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"ERROR: Session belum di-auth. Run dulu:", file=sys.stderr)
        print(f"  python3 {sys.argv[0]} --setup", file=sys.stderr)
        await client.disconnect()
        sys.exit(2)

    cutoff = None
    if hours_filter:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_filter)

    messages = []
    try:
        entity = await client.get_entity(channel)
        async for msg in client.iter_messages(entity, limit=limit):
            if cutoff and msg.date < cutoff:
                break
            if not msg.message:
                continue
            messages.append({
                "id": msg.id,
                "date": msg.date.isoformat(),
                "text": msg.message[:1500],
                "views": msg.views or 0,
                "urls": extract_urls(msg.message),
                "has_media": msg.media is not None,
            })
    finally:
        await client.disconnect()

    return messages


async def setup_auth():
    """Interactive first-time auth — phone + SMS code."""
    if not API_ID or not API_HASH:
        print("ERROR: Set TELEGRAM_API_ID + TELEGRAM_API_HASH dulu di .env", file=sys.stderr)
        print("Get di: https://my.telegram.org/apps", file=sys.stderr)
        sys.exit(2)

    Path(SESSION).parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(SESSION, API_ID, API_HASH)
    print(f"Session akan disimpan ke: {SESSION}")
    print(f"Telethon akan minta phone + SMS code. Follow prompt.\n")
    await client.start()  # interactive — prompts for phone + code
    me = await client.get_me()
    print(f"\n✓ Authorized as: {me.first_name} (@{me.username or 'no_username'})")
    print(f"✓ Session saved.")
    print(f"\n→ chmod 600 {SESSION}  (sensitive — anyone with file = your TG access)")
    await client.disconnect()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--channel", default="marketfeed",
                    help="Telegram channel username (no @, default: marketfeed)")
    ap.add_argument("--limit", type=int, default=10, help="max messages (default 10)")
    ap.add_argument("--hours", type=int, default=None,
                    help="filter messages dalam N jam terakhir")
    ap.add_argument("--output", default=None,
                    help="write JSON ke file (default: stdout)")
    ap.add_argument("--setup", action="store_true",
                    help="interactive first-time auth")
    args = ap.parse_args()

    if args.setup:
        asyncio.run(setup_auth())
        return

    msgs = asyncio.run(fetch_messages(args.channel, args.limit, args.hours))
    payload = {
        "channel": args.channel,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(msgs),
        "filter_hours": args.hours,
        "messages": msgs,
    }

    output = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        out_path = Path(os.path.expanduser(args.output))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output)
        print(f"Wrote {len(msgs)} messages to {out_path}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
