#!/usr/bin/env python3
"""
fetch_hyperliquid.py — Hyperliquid native data fetcher.

Sama output schema dengan fetch_market_data.py — drop-in replacement saat
EXCHANGE=hyperliquid. Tidak butuh ccxt; cuma stdlib + requests.

Env:
  COINS    Comma-separated, contoh: "BTC,ETH,SOL"  (tanpa /USDC)
  TF       1m | 5m | 15m | 1h | 4h | 1d           (default 15m)
  CANDLES  jumlah candle yang di-fetch              (default 60)
"""
import json
import os
import sys
import time
import urllib.request


HL_INFO = "https://api.hyperliquid.xyz/info"

COINS = os.getenv("COINS", "BTC,ETH,SOL").split(",")
TF = os.getenv("TF", "15m")
N_CANDLES = int(os.getenv("CANDLES", "60"))

# Hyperliquid candle interval = ms map
INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000,
    "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000,
}


def post(payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        HL_INFO, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_candles(coin: str, interval: str, n: int):
    if interval not in INTERVAL_MS:
        raise ValueError(f"interval tidak dikenal: {interval}")
    end = int(time.time() * 1000)
    start = end - INTERVAL_MS[interval] * (n + 1)
    payload = {
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": interval, "startTime": start, "endTime": end},
    }
    data = post(payload)
    # HL returns: [{"t":..,"T":..,"s":..,"i":..,"o":..,"c":..,"h":..,"l":..,"v":..,"n":..}, ...]
    out = []
    for c in data:
        out.append([
            int(c["t"]),
            float(c["o"]),
            float(c["h"]),
            float(c["l"]),
            float(c["c"]),
            float(c["v"]),
        ])
    return out


def fetch_meta_and_funding():
    """Return dict {coin: {funding, mark_px, oi}} dari metaAndAssetCtxs."""
    data = post({"type": "metaAndAssetCtxs"})
    if not isinstance(data, list) or len(data) != 2:
        return {}
    meta, ctxs = data
    out = {}
    universe = meta.get("universe", [])
    for i, asset in enumerate(universe):
        if i >= len(ctxs):
            break
        ctx = ctxs[i]
        out[asset["name"]] = {
            "funding": float(ctx.get("funding", 0)),
            "mark_px": float(ctx.get("markPx", 0)),
            "oi": float(ctx.get("openInterest", 0)),
        }
    return out


# === Schema match dengan fetch_market_data.py ===
def detect_fvg(candles, min_gap_pct=0.001):
    fvgs = []
    for i in range(1, len(candles) - 1):
        c1, c3 = candles[i - 1], candles[i + 1]
        # candle: [t, o, h, l, c, v] — index 2=high, 3=low
        if c1[2] < c3[3]:
            gap_pct = (c3[3] - c1[2]) / c1[2]
            if gap_pct >= min_gap_pct:
                fvgs.append({
                    "type": "bull",
                    "top": round(c3[3], 2),
                    "bottom": round(c1[2], 2),
                    "mid": round((c3[3] + c1[2]) / 2, 2),
                    "gap_pct": round(gap_pct * 100, 3),
                    "status": "fresh",
                })
        elif c1[3] > c3[2]:
            gap_pct = (c1[3] - c3[2]) / c3[2]
            if gap_pct >= min_gap_pct:
                fvgs.append({
                    "type": "bear",
                    "top": round(c1[3], 2),
                    "bottom": round(c3[2], 2),
                    "mid": round((c1[3] + c3[2]) / 2, 2),
                    "gap_pct": round(gap_pct * 100, 3),
                    "status": "fresh",
                })
    return fvgs


def fr_label(fr):
    # Hyperliquid funding di-quote per-hour, jadi scale-nya beda dari Binance.
    # Asumsi 1h funding; threshold disesuaikan.
    if fr < -0.0001:    return "EXTREME_SHORT (+1)"
    if fr < -0.00005:   return "SHORT_BIAS (+1)"
    if fr <= 0.00001:   return "NEUTRAL (0)"
    if fr <= 0.00005:   return "LONG_BIAS (0)"
    if fr <= 0.0001:    return "HEAVY_LONG (-1)"
    return "EXTREME_LONG (-1)"


def main():
    funding_map = fetch_meta_and_funding()
    results = []

    for coin in [c.strip() for c in COINS if c.strip()]:
        try:
            candles = fetch_candles(coin, TF, N_CANDLES)
            if not candles:
                results.append({"symbol": coin, "error": "no candles returned"})
                continue

            price = candles[-1][4]
            ctx = funding_map.get(coin, {})
            fr = ctx.get("funding", 0.0)
            oi = ctx.get("oi", 0.0)

            fvgs = detect_fvg(candles)
            active = [f for f in fvgs if f["status"] != "mitigated"]
            nearest = None
            if active:
                for f in active:
                    f["dist_pct"] = round(abs(price - f["mid"]) / price * 100, 2)
                nearest = min(active, key=lambda x: x["dist_pct"])
                if nearest["dist_pct"] > 3.0:
                    nearest = None

            closes = [c[4] for c in candles]
            ema21 = closes[0]
            k = 2 / 22
            for c in closes[1:]:
                ema21 = c * k + ema21 * (1 - k)

            results.append({
                "symbol": f"{coin}/USDC:USDC",
                "price": round(price, 2),
                "funding_rate": round(fr * 100, 5),  # %, per-hour di HL
                "funding_label": fr_label(fr),
                "open_interest": round(oi, 2),
                "ema21": round(ema21, 2),
                "macro_bias": "BULLISH" if price > ema21 else "BEARISH",
                "nearest_fvg": nearest,
                "active_fvg_count": len(active),
            })
            time.sleep(0.2)  # rate-limit polite
        except Exception as e:
            results.append({"symbol": coin, "error": str(e)})

    print(json.dumps({
        "timestamp": int(time.time()),
        "exchange": "hyperliquid",
        "timeframe": TF,
        "symbols": results,
    }, indent=2))


if __name__ == "__main__":
    main()
