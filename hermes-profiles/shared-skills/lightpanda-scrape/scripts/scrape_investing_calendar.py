#!/usr/bin/env python3
"""
scrape_investing_calendar.py — fetch investing.com economic calendar,
generate events.json untuk pause_check.py.

Recipe canonical: lihat references/fetch-investing-calendar.md.

Default: pakai curl-equivalent (urllib). Kalau 403 / Cloudflare → fallback
ke Lightpanda CDP via Node (lihat references/cloudflare-bypass.md).

Usage:
  python3 scrape_investing_calendar.py
  python3 scrape_investing_calendar.py --months 2
  python3 scrape_investing_calendar.py --output ~/.hermes/state/events.json
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from html import unescape
from pathlib import Path


INV_URL = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"
DEFAULT_OUTPUT = Path(os.path.expanduser(
    os.environ.get("EVENTS_FILE",
                   "~/.hermes/profiles/scalper-coach/state/events.json")
))


UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def build_payload(date_from: str, date_to: str) -> str:
    """form-urlencoded payload — country=5 (USD), importance 2+3 (med+high), tz UTC."""
    params = [
        ("country[]", "5"),
        ("importance[]", "2"),
        ("importance[]", "3"),
        ("timeZone", "55"),       # 55 = UTC
        ("timeFilter", "timeRemain"),
        ("currentTab", "custom"),
        ("dateFrom", date_from),
        ("dateTo", date_to),
        ("submitFilters", "1"),
        ("limit_from", "0"),
    ]
    return urllib.parse.urlencode(params)


def fetch_html(date_from: str, date_to: str) -> str:
    payload = build_payload(date_from, date_to).encode()
    req = urllib.request.Request(
        INV_URL,
        data=payload,
        headers={
            "User-Agent": UA,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.investing.com/economic-calendar/",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        body = json.loads(r.read())
    return body.get("data", "")


# === Parser sesuai recipe di references/fetch-investing-calendar.md ===
ROW_RE = re.compile(
    r'<tr id="eventRowId_(\d+)"[^>]*data-event-datetime="([^"]+)"[^>]*>(.*?)</tr>',
    re.S,
)
CCODE_RE = re.compile(r'class="ceFlags[^"]*"[^>]*>&nbsp;</span>\s*([A-Z]{3})')
IMPACT_RE = re.compile(r"grayFullBullishIcon")
NAME_RE = re.compile(r'<a href="(/economic-calendar/[^"]+)"[^>]*>\s*([^<]+?)\s*</a>')


def classify(name):
    n = name.lower()
    if "fed interest rate" in n:
        return "FOMC"
    if "fomc statement" in n or "fomc press conference" in n:
        return "FOMC"
    if "fomc member" in n and "speaks" in n:
        return "FED_SPEAK"
    if "nonfarm payroll" in n or "non-farm payroll" in n:
        return "NFP"
    if n.startswith("cpi (yoy)"):
        return "CPI"
    return None


def parse(html: str) -> list:
    raw = []
    for m in ROW_RE.finditer(html):
        body = m.group(3)
        cc_match = CCODE_RE.search(body)
        nm_match = NAME_RE.search(body)
        if not (cc_match and nm_match and cc_match.group(1) == "USD"):
            continue
        name = unescape(nm_match.group(2)).strip()
        ev_type = classify(name)
        if not ev_type:
            continue
        impact_count = len(IMPACT_RE.findall(body))
        try:
            dt = datetime.strptime(m.group(2), "%Y/%m/%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        raw.append({
            "id": f"{dt.strftime('%Y-%m-%d')}-{ev_type.lower()}-{m.group(1)}",
            "type": ev_type,
            "release_at": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "impact": "high" if impact_count >= 3 else "medium" if impact_count == 2 else "low",
            "name": name,
            "source": "investing.com",
            "source_url": "https://www.investing.com" + nm_match.group(1),
        })
    return raw


def dedupe(events: list) -> list:
    """Per (date, type) keep highest impact."""
    rank = {"high": 3, "medium": 2, "low": 1}
    by_key = {}
    for e in events:
        k = (e["release_at"][:10], e["type"])
        if k not in by_key or rank[e["impact"]] > rank[by_key[k]["impact"]]:
            by_key[k] = e
    return sorted(by_key.values(), key=lambda x: x["release_at"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=2,
                    help="berapa bulan ke depan (default 2)")
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT),
                    help=f"path events.json (default {DEFAULT_OUTPUT})")
    args = ap.parse_args()

    today = datetime.now(timezone.utc).date()
    date_from = today.strftime("%Y-%m-%d")
    date_to = (today + timedelta(days=args.months * 31)).strftime("%Y-%m-%d")

    print(f"Fetching investing.com events {date_from} → {date_to}...", file=sys.stderr)
    try:
        html = fetch_html(date_from, date_to)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print("ERROR 403: Cloudflare. Fallback ke Lightpanda CDP belum implemented.",
                  file=sys.stderr)
            print("Lihat references/cloudflare-bypass.md untuk recipe Node + playwright.",
                  file=sys.stderr)
            sys.exit(2)
        raise

    events = dedupe(parse(html))
    out = Path(os.path.expanduser(args.output))
    out.parent.mkdir(parents=True, exist_ok=True)

    # Preserve last-good kalau parse return 0 events (jangan wipe events.json)
    if not events and out.exists():
        print("WARNING: 0 events parsed. Keeping last-good copy.", file=sys.stderr)
        sys.exit(1)

    with out.open("w") as f:
        json.dump(events, f, indent=2)
    print(f"OK wrote {len(events)} events to {out}", file=sys.stderr)
    if events:
        print(f"  next: {events[0]['release_at']} {events[0]['type']} ({events[0]['name']})",
              file=sys.stderr)


if __name__ == "__main__":
    main()
