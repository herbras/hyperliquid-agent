#!/usr/bin/env python3
"""
fetch_bybit.py — Bybit V5 public market data fetcher.

Sama output schema dengan fetch_hyperliquid.py & fetch_market_data.py.
Public API only (no auth) — pakai untuk scout / sniper bias scan.

Untuk eksekusi trade, install official Bybit AI skill:
  https://github.com/bybit-exchange/skills

Env:
  SYMBOLS     Comma-separated: "BTCUSDT,ETHUSDT,SOLUSDT" (no slash, V5 format)
  TF          1m | 5m | 15m | 30m | 1h | 2h | 4h | 1d (default 15m)
  CANDLES     jumlah candle (default 60)
  CATEGORY    linear (USDT/USDC perp, default) | inverse | spot
  BYBIT_BASE  override base URL (mainnet default)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request


BASE = os.getenv("BYBIT_BASE", "https://api.bybit.com")
CATEGORY = os.getenv("CATEGORY", "linear")
SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",") if s.strip()]
TF = os.getenv("TF", "15m")
N_CANDLES = int(os.getenv("CANDLES", "60"))


# Bybit V5 interval map: tf-string → API interval value
INTERVAL = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "2h": "120", "4h": "240", "6h": "360", "12h": "720",
    "1d": "D", "1w": "W", "1M": "M",
}


def get(path, params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE}{path}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "scout/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        body = json.loads(r.read())
    if body.get("retCode") != 0:
        raise RuntimeError(f"Bybit API error: {body.get('retCode')} {body.get('retMsg')}")
    return body["result"]


def fetch_candles(symbol, interval, n):
    if interval not in INTERVAL:
        raise ValueError(f"interval tidak dikenal: {interval}")
    res = get("/v5/market/kline", {
        "category": CATEGORY,
        "symbol": symbol,
        "interval": INTERVAL[interval],
        "limit": n,
    })
    # V5 list = newest first → reverse jadi oldest first (sesuai schema)
    out = []
    for c in reversed(res.get("list", [])):
        out.append([
            int(c[0]),
            float(c[1]), float(c[2]), float(c[3]), float(c[4]),
            float(c[5]),
        ])
    return out


def fetch_ticker(symbol):
    res = get("/v5/market/tickers", {"category": CATEGORY, "symbol": symbol})
    items = res.get("list", [])
    if not items:
        return None
    t = items[0]
    return {
        "last_price": float(t.get("lastPrice", 0) or 0),
        "funding": float(t.get("fundingRate", 0) or 0),
        "open_interest": float(t.get("openInterest", 0) or 0),
        "oi_value": float(t.get("openInterestValue", 0) or 0),
        "volume_24h": float(t.get("volume24h", 0) or 0),
    }


# === Schema match dengan fetch_hyperliquid.py ===
def detect_fvg(candles, min_gap_pct=0.001):
    fvgs = []
    for i in range(1, len(candles) - 1):
        c1, c3 = candles[i - 1], candles[i + 1]
        if c1[2] < c3[3]:
            gap_pct = (c3[3] - c1[2]) / c1[2]
            if gap_pct >= min_gap_pct:
                fvgs.append({
                    "type": "bull",
                    "top": round(c3[3], 2), "bottom": round(c1[2], 2),
                    "mid": round((c3[3] + c1[2]) / 2, 2),
                    "gap_pct": round(gap_pct * 100, 3), "status": "fresh",
                })
        elif c1[3] > c3[2]:
            gap_pct = (c1[3] - c3[2]) / c3[2]
            if gap_pct >= min_gap_pct:
                fvgs.append({
                    "type": "bear",
                    "top": round(c1[3], 2), "bottom": round(c3[2], 2),
                    "mid": round((c1[3] + c3[2]) / 2, 2),
                    "gap_pct": round(gap_pct * 100, 3), "status": "fresh",
                })
    return fvgs


def fr_label(fr):
    """Bybit funding = per-8-hours (mirip Binance) — threshold ikut binance scale."""
    if fr < -0.001:    return "EXTREME_SHORT (+1)"
    if fr < -0.0005:   return "SHORT_BIAS (+1)"
    if fr <= 0.0001:   return "NEUTRAL (0)"
    if fr <= 0.0005:   return "LONG_BIAS (0)"
    if fr <= 0.001:    return "HEAVY_LONG (-1)"
    return "EXTREME_LONG (-1)"


def main():
    results = []
    for symbol in SYMBOLS:
        try:
            candles = fetch_candles(symbol, TF, N_CANDLES)
            if not candles:
                results.append({"symbol": symbol, "error": "no candles"})
                continue
            ticker = fetch_ticker(symbol) or {}

            price = candles[-1][4]
            fr = ticker.get("funding", 0.0)
            oi = ticker.get("open_interest", 0.0)

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
                "symbol": symbol,
                "price": round(price, 2),
                "funding_rate": round(fr * 100, 4),  # %, 8h scale
                "funding_label": fr_label(fr),
                "open_interest": round(oi, 2),
                "ema21": round(ema21, 2),
                "macro_bias": "BULLISH" if price > ema21 else "BEARISH",
                "nearest_fvg": nearest,
                "active_fvg_count": len(active),
            })
            time.sleep(0.15)  # rate-limit polite (Bybit allows ~600 req/5s public)
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e)})

    print(json.dumps({
        "timestamp": int(time.time()),
        "exchange": "bybit",
        "category": CATEGORY,
        "timeframe": TF,
        "symbols": results,
    }, indent=2))


if __name__ == "__main__":
    main()
