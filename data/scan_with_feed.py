#!/usr/bin/env python3
"""
scan_with_feed.py — wrapper yang gabungin market data + telegram feed.

Run:
  1. fetch_hyperliquid.py (atau fetch_market_data.py / fetch_bybit.py per env DATA_SOURCE)
  2. fetch_telegram_feed.py (skip kalau session belum auth)
  3. Output combined JSON ke stdout untuk konsumsi scout cron

Env:
  DATA_SOURCE        hl | bybit | ccxt (default: hl)
  TF                 timeframe (default 1h, sesuai bias frame STRATEGI-15M)
  COINS / SYMBOLS    forwarded ke fetcher
  TELEGRAM_CHANNEL   default 'marketfeed'
  TELEGRAM_HOURS     filter feed dalam N jam (default 4)
  TELEGRAM_LIMIT     max messages (default 8)
  HL_REPO            path ke repo (default ~/Documents/panduan-openclaw/hyperliquid)

Output:
  {
    "fetched_at": "...",
    "market": {<output dari data fetcher>},
    "feed": {<output dari telegram fetcher, atau {"skipped": "reason"}>}
  }
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


HL_REPO = os.path.expanduser(os.environ.get(
    "HL_REPO", "~/Documents/panduan-openclaw/hyperliquid"
))
DATA_SOURCE = os.environ.get("DATA_SOURCE", "hl")
TG_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "marketfeed")
TG_HOURS = int(os.environ.get("TELEGRAM_HOURS", "4"))
TG_LIMIT = int(os.environ.get("TELEGRAM_LIMIT", "8"))


def run_market():
    """Run data fetcher per DATA_SOURCE, return parsed JSON."""
    sources = {
        "hl": "data/fetch_hyperliquid.py",
        "bybit": "data/fetch_bybit.py",
        "ccxt": "data/fetch_market_data.py",
    }
    if DATA_SOURCE not in sources:
        return {"error": f"DATA_SOURCE '{DATA_SOURCE}' tidak dikenal"}

    script = os.path.join(HL_REPO, sources[DATA_SOURCE])
    try:
        proc = subprocess.run(
            ["python3", script], capture_output=True, text=True,
            timeout=60, env={**os.environ},
        )
        if proc.returncode != 0:
            return {"error": proc.stderr.strip()[:300]}
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "market fetch timeout 60s"}
    except json.JSONDecodeError as e:
        return {"error": f"market JSON parse: {e}"}


def run_telegram():
    """Run telegram fetcher. Graceful degrade kalau belum auth / no creds."""
    script = os.path.join(HL_REPO, "data/fetch_telegram_feed.py")
    if not os.environ.get("TELEGRAM_API_ID") or not os.environ.get("TELEGRAM_API_HASH"):
        return {"skipped": "TELEGRAM_API_ID/HASH not set"}
    try:
        proc = subprocess.run(
            ["python3", script,
             "--channel", TG_CHANNEL,
             "--hours", str(TG_HOURS),
             "--limit", str(TG_LIMIT)],
            capture_output=True, text=True, timeout=30,
            env={**os.environ},
        )
        if proc.returncode != 0:
            return {"skipped": proc.stderr.strip()[:200]}
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        return {"skipped": "telegram fetch timeout 30s"}
    except json.JSONDecodeError as e:
        return {"skipped": f"telegram JSON parse: {e}"}


def main():
    market = run_market()
    feed = run_telegram()

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "data_source": DATA_SOURCE,
        "market": market,
        "feed": feed,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
