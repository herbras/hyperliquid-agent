#!/usr/bin/env python3
"""
exchange_picker.py — discover, test, and pick preferred ccxt exchange.

ccxt support 100+ exchange. Tool ini bantu user pilih yang:
- Reachable dari mesin/server kamu (penting untuk VPS yang region-blocked)
- Punya pair yang kamu butuhkan
- Format simbol yang sesuai
- Capability-nya match (spot / swap / futures / options)

Usage:
  python3 exchange_picker.py list                       # popular exchanges + feature matrix
  python3 exchange_picker.py test                       # reachability test (curated)
  python3 exchange_picker.py test okx kucoin bitget     # test specific
  python3 exchange_picker.py test --all                 # test ALL ccxt exchanges (slow)
  python3 exchange_picker.py info okx                   # capabilities + sample symbol
  python3 exchange_picker.py try okx --pair BTC/USDT:USDT --tf 15m  # live fetch sample
  python3 exchange_picker.py recommend                  # rank by reachability + features

Output recommend → save ke config:
  EXCHANGE_FALLBACK=okx,kucoin,bitget python3 fetch_market_data.py
"""
import argparse
import asyncio
import json
import sys
import time

try:
    import ccxt.async_support as ccxt_async
    import ccxt as ccxt_sync
except ImportError:
    print("ERROR: pip install ccxt --break-system-packages", file=sys.stderr)
    sys.exit(1)


# Curated list — exchanges populer untuk crypto perp/spot scalping
# Field "perp_id" = ccxt id untuk perp/swap variant kalau ada (sebagian
# exchange punya separate ID untuk futures, sebagian unified).
POPULAR = [
    # id          perp_id          region    note
    {"id": "binance",      "perp_id": "binanceusdm",  "region": "global",  "note": "Largest. Often blocked di VPS."},
    {"id": "bybit",        "perp_id": "bybit",        "region": "global",  "note": "Deep liquidity. Geo-restricted."},
    {"id": "okx",          "perp_id": "okx",          "region": "global",  "note": "Strong perp. Good liquidity Asia pairs."},
    {"id": "kucoin",       "perp_id": "kucoinfutures","region": "global",  "note": "Many altcoins. Less restricted."},
    {"id": "bitget",       "perp_id": "bitget",       "region": "global",  "note": "Growing, Asia-friendly."},
    {"id": "mexc",         "perp_id": "mexc",         "region": "global",  "note": "Many small-cap pairs."},
    {"id": "gate",         "perp_id": "gate",         "region": "global",  "note": "Wide pair selection."},
    {"id": "htx",          "perp_id": "htx",          "region": "global",  "note": "Formerly Huobi."},
    {"id": "kraken",       "perp_id": "krakenfutures","region": "US/EU",   "note": "Regulated. Slower API."},
    {"id": "bitmex",       "perp_id": "bitmex",       "region": "global",  "note": "Original perp exchange."},
    {"id": "deribit",      "perp_id": "deribit",      "region": "global",  "note": "Options + perp. ETH/BTC focus."},
    {"id": "phemex",       "perp_id": "phemex",       "region": "global",  "note": "Asia-friendly."},
    {"id": "coinbase",     "perp_id": None,           "region": "US",      "note": "Spot only via ccxt. No perp."},
    {"id": "hyperliquid",  "perp_id": "hyperliquid",  "region": "on-chain","note": "On-chain perp. Use fetch_hyperliquid.py for native."},
]


def cmd_list(args):
    """Print feature matrix dari curated list."""
    print(f"=== Popular ccxt exchanges ({len(POPULAR)}) ===\n")
    print(f"{'id':<14} {'perp_id':<18} {'region':<10} note")
    print("-" * 90)
    for e in POPULAR:
        perp = e["perp_id"] or "-"
        print(f"{e['id']:<14} {perp:<18} {e['region']:<10} {e['note']}")
    print(f"\nTotal ccxt exchanges available: {len(ccxt_sync.exchanges)}")
    print(f"For full list: python3 -c 'import ccxt; print(ccxt.exchanges)'")


async def _test_one(ex_id, timeout=8):
    """Test reachability + load_markets dari satu exchange."""
    if ex_id not in ccxt_async.exchanges:
        return {"id": ex_id, "ok": False, "reason": "not in ccxt"}
    ex = None
    try:
        cls = getattr(ccxt_async, ex_id)
        ex = cls({"enableRateLimit": True, "timeout": timeout * 1000})
        t0 = time.time()
        await ex.load_markets()
        dt = round((time.time() - t0) * 1000)
        n = len(ex.markets)
        sample = None
        for s in ex.markets:
            if "BTC" in s and ("USDT" in s or "USDC" in s):
                sample = s
                break
        return {"id": ex_id, "ok": True, "ms": dt, "markets": n, "sample": sample}
    except Exception as e:
        return {"id": ex_id, "ok": False, "reason": str(e)[:80]}
    finally:
        if ex is not None:
            try:
                await ex.close()
            except Exception:
                pass


async def _test_many(ids):
    return await asyncio.gather(*[_test_one(x) for x in ids])


def cmd_test(args):
    if args.all:
        ids = list(ccxt_sync.exchanges)
        print(f"Testing ALL {len(ids)} ccxt exchanges (parallel, ~30s)...\n")
    elif args.exchanges:
        ids = args.exchanges
    else:
        # Default: curated popular list
        ids = [e["id"] for e in POPULAR]
        # Ditambah perp variant kalau beda
        for e in POPULAR:
            if e["perp_id"] and e["perp_id"] != e["id"]:
                ids.append(e["perp_id"])

    results = asyncio.run(_test_many(ids))

    ok = sorted([r for r in results if r["ok"]], key=lambda x: x["ms"])
    fail = [r for r in results if not r["ok"]]

    print(f"=== Reachable ({len(ok)}/{len(results)}) ===")
    for r in ok:
        print(f"  ✓ {r['id']:<22} {r['ms']:>4}ms  {r['markets']:>5} markets   sample: {r['sample']}")

    if fail and not args.quiet:
        print(f"\n=== Failed ({len(fail)}) ===")
        for r in fail:
            print(f"  ✗ {r['id']:<22} {r['reason']}")

    if ok:
        top = [r["id"] for r in ok[:5]]
        print(f"\nRecommended fallback chain (top 5 fastest):")
        print(f"  EXCHANGE_FALLBACK={','.join(top)}")


def cmd_info(args):
    """Detail capability dari satu exchange."""
    ex_id = args.exchange
    if ex_id not in ccxt_sync.exchanges:
        print(f"ERROR: '{ex_id}' tidak dikenal di ccxt", file=sys.stderr)
        print(f"Cari mirip: " + ", ".join(
            x for x in ccxt_sync.exchanges if ex_id.lower() in x.lower())[:200])
        sys.exit(2)

    cls = getattr(ccxt_sync, ex_id)
    ex = cls({"enableRateLimit": True})

    print(f"=== {ex_id} ===")
    print(f"Name      : {ex.name}")
    print(f"Country   : {', '.join(ex.countries) if isinstance(ex.countries, list) else ex.countries}")
    print(f"URLs      : {ex.urls.get('www', 'n/a')}")
    print(f"\nCapabilities:")
    has = ex.has
    interesting = ["fetchOHLCV", "fetchFundingRate", "fetchOpenInterest",
                   "fetchTicker", "fetchTickers", "createOrder", "cancelOrder",
                   "fetchPositions", "fetchBalance"]
    for cap in interesting:
        v = has.get(cap, False)
        sym = "✓" if v is True else "~" if v == "emulated" else "✗"
        print(f"  {sym} {cap}")

    print(f"\nTimeframes: {', '.join(ex.timeframes.keys()) if hasattr(ex, 'timeframes') and ex.timeframes else 'n/a'}")
    print(f"\nRate limit: {ex.rateLimit}ms between requests")

    print(f"\nFor symbol format:  python3 exchange_picker.py try {ex_id} --pair BTC/USDT")


async def _try_fetch(ex_id, pair, tf, limit):
    cls = getattr(ccxt_async, ex_id)
    ex = cls({"enableRateLimit": True, "timeout": 15000})
    try:
        await ex.load_markets()
        if pair not in ex.markets:
            # Cari pair mirip
            similar = [s for s in ex.markets if pair.split("/")[0] in s][:5]
            await ex.close()
            return {"ok": False, "reason": f"pair '{pair}' tidak ada. Mirip: {similar}"}
        candles = await ex.fetch_ohlcv(pair, tf, limit=limit)
        ticker = await ex.fetch_ticker(pair)
        await ex.close()
        return {
            "ok": True,
            "candles_fetched": len(candles),
            "last_close": candles[-1][4] if candles else None,
            "ticker_last": ticker.get("last"),
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "spread_bps": round((ticker["ask"] - ticker["bid"]) / ticker["last"] * 10000, 2)
                          if ticker.get("ask") and ticker.get("bid") else None,
        }
    except Exception as e:
        try:
            await ex.close()
        except Exception:
            pass
        return {"ok": False, "reason": str(e)[:200]}


def cmd_try(args):
    """Live fetch sample candles + ticker dari satu exchange."""
    res = asyncio.run(_try_fetch(args.exchange, args.pair, args.tf, args.limit))
    print(json.dumps({"exchange": args.exchange, "pair": args.pair, "tf": args.tf, **res},
                     indent=2))


def cmd_recommend(args):
    """Test curated, lalu output ranking + suggested config."""
    ids = [e["perp_id"] or e["id"] for e in POPULAR]
    print(f"Testing {len(ids)} popular exchanges...\n")
    results = asyncio.run(_test_many(ids))
    ok = sorted([r for r in results if r["ok"]], key=lambda x: x["ms"])

    print(f"=== Recommended fallback chain (untuk fetch_market_data.py) ===\n")
    if not ok:
        print("⚠ Tidak ada exchange yang reachable. Cek koneksi internet / firewall.")
        return

    top = [r["id"] for r in ok[:5]]
    print(f"Top 5 fastest reachable:")
    for i, r in enumerate(ok[:5], 1):
        print(f"  {i}. {r['id']:<20} ({r['ms']}ms, sample: {r['sample']})")

    print(f"\nSet ke .env atau export di shell:")
    print(f"  EXCHANGE_FALLBACK={','.join(top)}")
    print(f"\nUsage di fetch_market_data.py:")
    print(f"  EXCHANGE_FALLBACK={','.join(top)} \\")
    print(f"  SYMBOLS='BTC/USDT:USDT,ETH/USDT:USDT' TF=15m \\")
    print(f"  python3 fetch_market_data.py")


def main():
    ap = argparse.ArgumentParser(description="Discover & test ccxt exchanges")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Show curated popular exchanges")

    p_test = sub.add_parser("test", help="Test reachability")
    p_test.add_argument("exchanges", nargs="*", help="exchange ids; default = curated")
    p_test.add_argument("--all", action="store_true", help="test ALL ccxt exchanges")
    p_test.add_argument("--quiet", action="store_true")

    p_info = sub.add_parser("info", help="Show capabilities")
    p_info.add_argument("exchange")

    p_try = sub.add_parser("try", help="Live fetch sample")
    p_try.add_argument("exchange")
    p_try.add_argument("--pair", default="BTC/USDT")
    p_try.add_argument("--tf", default="15m")
    p_try.add_argument("--limit", type=int, default=10)

    sub.add_parser("recommend", help="Test + rank + suggest config")

    args = ap.parse_args()
    {"list": cmd_list, "test": cmd_test, "info": cmd_info,
     "try": cmd_try, "recommend": cmd_recommend}[args.cmd](args)


if __name__ == "__main__":
    main()
