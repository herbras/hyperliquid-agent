#!/usr/bin/env python3
"""
pause_check.py — baca events.json, set/unset PAUSE.flag berdasarkan jarak
ke event terdekat.

Window pause:
  CPI / NFP   : -30 min ... +60 min  (90 menit total)
  FOMC        : -30 min ... +120 min (150 menit, ada press conference)
  FED_SPEAK   : -15 min ... +30 min  (45 menit, opsional)

Pakai:
  python3 pause_check.py                       # auto check & set/unset
  python3 pause_check.py --status              # cek tanpa modify flag
  python3 pause_check.py --events-file PATH    # custom path

Cron (tiap 5 menit di profile coach):
  */5 * * * *  python3 ~/Documents/.../pause_check.py
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


PAUSE_FLAG = Path(os.path.expanduser(
    os.environ.get("PAUSE_FLAG",
                   "~/.hermes/profiles/scalper-scout/PAUSE.flag")
))
EVENTS_FILE = Path(os.path.expanduser(
    os.environ.get("EVENTS_FILE",
                   "~/.hermes/profiles/scalper-coach/state/events.json")
))


# Window pause per type (pre_min, post_min)
WINDOWS = {
    "CPI":       (30, 60),
    "NFP":       (30, 60),
    "FOMC":      (30, 120),
    "FED_SPEAK": (15, 30),
}


def load_events():
    if not EVENTS_FILE.exists():
        return []
    with EVENTS_FILE.open() as f:
        return json.load(f)


def in_window(event, now):
    """Return (in_window, delta_minutes_from_release)."""
    pre, post = WINDOWS.get(event["type"], (30, 60))
    release = datetime.fromisoformat(event["release_at"].replace("Z", "+00:00"))
    delta = release - now
    delta_min = int(delta.total_seconds() / 60)
    if -post <= delta_min <= pre:
        return True, delta_min
    return False, delta_min


def find_active(events, now):
    """Events yang lagi dalam window pause sekarang."""
    out = []
    for e in events:
        active, delta_min = in_window(e, now)
        if active:
            out.append((e, delta_min))
    return out


def write_pause(active):
    """Tulis PAUSE.flag dengan info events aktif."""
    PAUSE_FLAG.parent.mkdir(parents=True, exist_ok=True)
    lines = ["⏸ PAUSE — economic event window aktif:"]
    for e, delta_min in active:
        when = f"in {delta_min}m" if delta_min > 0 else f"{abs(delta_min)}m ago"
        lines.append(f"  • {e['release_at'][11:16]}Z {e['type']} ({e['name']}) — {when}")
    PAUSE_FLAG.write_text("\n".join(lines) + "\n")


def is_event_pause():
    """True kalau PAUSE.flag dibuat oleh script ini (bukan manual halt)."""
    if not PAUSE_FLAG.exists():
        return False
    return "economic event window" in PAUSE_FLAG.read_text()


def cmd_check():
    events = load_events()
    if not events:
        print(f"WARNING: events.json kosong / tidak ada di {EVENTS_FILE}",
              file=sys.stderr)
        print("Run: python3 shared-skills/lightpanda-scrape/scripts/scrape_investing_calendar.py",
              file=sys.stderr)
        return 0

    now = datetime.now(timezone.utc)
    active = find_active(events, now)

    if active:
        write_pause(active)
        for e, dm in active:
            when = f"in {dm}m" if dm > 0 else f"{abs(dm)}m ago"
            print(f"⏸ PAUSE active: {e['release_at']} {e['type']} ({when})")
    else:
        # Cek: kalau PAUSE.flag exists & dibuat script ini → clear
        if is_event_pause():
            PAUSE_FLAG.unlink()
            print("✅ Event window cleared. Trading resumed.")
        else:
            print("OK — no event in pause window.")
            # Kalau ada event terdekat, info-kan
            future = [(e, in_window(e, now)[1]) for e in events]
            future = [(e, dm) for e, dm in future if dm > 0]
            if future:
                e, dm = min(future, key=lambda x: x[1])
                hours = dm / 60
                print(f"   Next: {e['type']} in {hours:.1f}h ({e['release_at']})")
    return 0


def cmd_status():
    events = load_events()
    print(f"events.json: {EVENTS_FILE} ({'exists' if EVENTS_FILE.exists() else 'MISSING'})")
    print(f"PAUSE.flag : {PAUSE_FLAG} ({'set' if PAUSE_FLAG.exists() else 'clear'})")
    if PAUSE_FLAG.exists():
        print(f"  content: {PAUSE_FLAG.read_text().strip()}")
    print(f"events: {len(events)}")
    if events:
        now = datetime.now(timezone.utc)
        upcoming = sorted(
            ((e, in_window(e, now)[1]) for e in events),
            key=lambda x: abs(x[1])
        )[:5]
        print("\n5 events terdekat:")
        for e, dm in upcoming:
            sign = "+" if dm >= 0 else ""
            hours = dm / 60
            print(f"  {sign}{hours:6.1f}h  {e['release_at']}  {e['type']:10s}  "
                  f"{e['name']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true",
                    help="show status tanpa modify flag")
    ap.add_argument("--events-file", help="override events.json path")
    args = ap.parse_args()

    if args.events_file:
        global EVENTS_FILE
        EVENTS_FILE = Path(os.path.expanduser(args.events_file))

    if args.status:
        cmd_status()
    else:
        cmd_check()


if __name__ == "__main__":
    main()
