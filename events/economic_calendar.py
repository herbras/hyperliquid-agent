#!/usr/bin/env python3
"""
economic_calendar.py — fetch economic events high-impact, set/unset PAUSE.flag.

Strategi: scalping di-pause 30 menit sebelum & 15 menit sesudah event
high-impact (CPI, FOMC, NFP, PCE, dll). Per STRATEGI-15M.md skip rule.

Source: pakai Trading Economics public RSS atau ForexFactory JSON
(no auth needed for upcoming events). Default: simple curated list dari
calendar API gratis.

Usage:
  python3 economic_calendar.py check          # cek events dalam 1 jam ke depan
  python3 economic_calendar.py upcoming 24    # list events dalam N jam
  python3 economic_calendar.py force-pause 30 # paksa pause N menit
  python3 economic_calendar.py clear-pause    # remove flag
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path


PAUSE_FLAG = Path(os.path.expanduser(
    os.environ.get("PAUSE_FLAG",
                   "~/.hermes/profiles/scalper-scout/PAUSE.flag")
))

# Fallback static list — kalau API down. Update manual setiap awal bulan.
# Format: "YYYY-MM-DDTHH:MM:00Z", impact level, description
STATIC_EVENTS = [
    # template — populate dari TradingEconomics atau ForexFactory
    # ("2025-05-13T12:30:00Z", "high", "US CPI"),
    # ("2025-05-15T18:00:00Z", "high", "FOMC Minutes"),
]

# Public ForexFactory weekly JSON — no auth
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def fetch_events():
    """Return list of {time: datetime, impact: str, title: str, currency: str}."""
    try:
        req = urllib.request.Request(FF_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        events = []
        for e in data:
            try:
                # ForexFactory format: "2025-05-13T08:30:00-04:00"
                t = datetime.fromisoformat(e["date"])
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                else:
                    t = t.astimezone(timezone.utc)
                events.append({
                    "time": t,
                    "impact": e.get("impact", "low").lower(),
                    "title": e.get("title", ""),
                    "currency": e.get("country", e.get("currency", "")),
                })
            except Exception:
                continue
        return events
    except Exception as ex:
        print(f"WARNING: fetch_events failed: {ex}. Falling back to static.",
              file=sys.stderr)
        events = []
        for t_str, impact, title in STATIC_EVENTS:
            t = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
            events.append({"time": t, "impact": impact, "title": title, "currency": "USD"})
        return events


def filter_high_impact_usd(events):
    """USD high-impact events relevan untuk crypto (CPI/FOMC/NFP)."""
    keywords = ["CPI", "FOMC", "NFP", "Non-Farm", "PCE", "Fed Funds",
                "Fed Chair", "Powell", "Unemployment Rate", "GDP",
                "Producer Price", "PPI", "Core CPI", "Core PCE"]
    out = []
    for e in events:
        if e["impact"] != "high":
            continue
        if e["currency"] not in ("USD", "United States", ""):
            continue
        if not any(kw.lower() in e["title"].lower() for kw in keywords) and "USD" not in e["currency"]:
            continue
        out.append(e)
    return out


def cmd_check(args):
    """Cek apakah ada event high-impact dalam 30 menit ke depan ATAU 15 menit
    di belakang. Set/unset PAUSE.flag accordingly."""
    now = datetime.now(timezone.utc)
    pause_window_pre = timedelta(minutes=30)
    pause_window_post = timedelta(minutes=15)

    events = filter_high_impact_usd(fetch_events())
    in_window = []
    for e in events:
        delta = e["time"] - now
        if -pause_window_post <= delta <= pause_window_pre:
            in_window.append((e, delta))

    if in_window:
        # Aktifkan PAUSE
        PAUSE_FLAG.parent.mkdir(parents=True, exist_ok=True)
        msg_lines = ["⏸ PAUSE — economic event window aktif:"]
        for e, delta in in_window:
            mins = int(delta.total_seconds() / 60)
            when = f"in {mins}m" if mins > 0 else f"{abs(mins)}m ago"
            msg_lines.append(f"  • {e['time'].strftime('%H:%M UTC')} {e['title']} ({when})")
        msg = "\n".join(msg_lines)
        PAUSE_FLAG.write_text(msg + "\n")
        print(msg)
    else:
        # Cek apakah PAUSE.flag dibuat oleh script ini (bukan manual)
        if PAUSE_FLAG.exists():
            content = PAUSE_FLAG.read_text()
            if "economic event window" in content:
                PAUSE_FLAG.unlink()
                print("✅ Economic event window cleared. Trading resumed.")
                return
        print("OK — no high-impact event in pause window.")


def cmd_upcoming(args):
    hours = int(args[0]) if args else 24
    cutoff = datetime.now(timezone.utc) + timedelta(hours=hours)
    events = filter_high_impact_usd(fetch_events())
    upcoming = [e for e in events if datetime.now(timezone.utc) <= e["time"] <= cutoff]
    if not upcoming:
        print(f"No high-impact USD events in next {hours}h.")
        return
    print(f"=== Upcoming high-impact events (next {hours}h) ===")
    for e in sorted(upcoming, key=lambda x: x["time"]):
        delta_min = int((e["time"] - datetime.now(timezone.utc)).total_seconds() / 60)
        print(f"  {e['time'].strftime('%a %d %H:%M UTC')}  +{delta_min}m  {e['title']}")


def cmd_force_pause(args):
    minutes = int(args[0]) if args else 30
    PAUSE_FLAG.parent.mkdir(parents=True, exist_ok=True)
    until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    PAUSE_FLAG.write_text(
        f"⏸ MANUAL PAUSE until {until.isoformat()}Z (~{minutes} min)\n"
    )
    print(f"OK PAUSE active for {minutes} min.")


def cmd_clear_pause(args):
    if PAUSE_FLAG.exists():
        PAUSE_FLAG.unlink()
        print("OK PAUSE cleared.")
    else:
        print("No active pause.")


COMMANDS = {
    "check": cmd_check,
    "upcoming": cmd_upcoming,
    "force-pause": cmd_force_pause,
    "clear-pause": cmd_clear_pause,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
