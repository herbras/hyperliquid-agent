#!/usr/bin/env python3
"""
backtest_15m.py — MVP backtest untuk strategi 15m Setup A.

Replay candle 1h (bias) + 15m (execution) dari satu pair, simulate Setup A
saja (continuation): bias 1h bullish + pullback ke FVG/OB + 15m close di
Discount → entry. SL 0.4% di bawah low candle setup, TP1 di swing high
sebelumnya, TP2 di +2x R.

Limitasi MVP:
- Setup A only (B/C tidak ada — terlalu kompleks untuk MVP)
- Pakai FVG sebagai proxy OB (FVG lebih mudah di-detect dari raw candle)
- Macro bias dari ema21 1h (proxy Swing BOS)
- Tidak account untuk slippage / fees / funding cost
- Window filter: hanya entry di 00-04 atau 13-17 UTC

Usage:
  python3 backtest_15m.py BTC 30        # backtest BTC, 30 hari ke belakang
  python3 backtest_15m.py SOL 14 hl     # 14 hari, source=Hyperliquid native
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta


# === Config ===
SL_BUFFER_PCT = 0.004    # 0.4% per STRATEGI-15M.md (be wide)
MAX_SL_PCT = 0.015       # 1.5% — di atas ini SKIP
RR_MIN = 2.0             # 1:2 minimum
TP2_RR = 4.0             # TP2 di +4R untuk 30% pos
TIMER_CANDLES = 12       # 12 × 15m = 3 jam
TP1_PCT = 0.5            # close 50% di TP1
TP2_PCT = 0.3            # close 30% di TP2
TRAIL_PCT = 0.2          # 20% trailing
ACTIVE_HOURS = set(range(0, 4)) | set(range(13, 17))


def fetch_hl_candles(coin: str, interval: str, hours_back: int):
    """Hyperliquid native candleSnapshot."""
    intvl_ms = {"1h": 3_600_000, "15m": 900_000}[interval]
    end = int(time.time() * 1000)
    start = end - hours_back * 3_600_000
    payload = {"type": "candleSnapshot",
               "req": {"coin": coin, "interval": interval,
                       "startTime": start, "endTime": end}}
    req = urllib.request.Request(
        "https://api.hyperliquid.xyz/info",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    return [[int(c["t"]), float(c["o"]), float(c["h"]), float(c["l"]),
             float(c["c"]), float(c["v"])] for c in data]


def fetch_ccxt_candles(symbol: str, interval: str, hours_back: int):
    import ccxt  # type: ignore
    ex = ccxt.binanceusdm({"enableRateLimit": True})
    intvl_ms = ex.parse_timeframe(interval) * 1000
    since = int(time.time() * 1000) - hours_back * 3_600_000
    candles = []
    while True:
        batch = ex.fetch_ohlcv(symbol, interval, since=since, limit=500)
        if not batch:
            break
        candles.extend(batch)
        if len(batch) < 500:
            break
        since = batch[-1][0] + intvl_ms
        time.sleep(0.3)
    return candles


def ema(values, period):
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def detect_bull_fvg_at(candles, i):
    """Cek apakah ada bull FVG yang terbentuk di candle index i (gap antara i-1 dan i+1)."""
    if i < 1 or i >= len(candles) - 1:
        return None
    c_prev, c_next = candles[i - 1], candles[i + 1]
    if c_prev[2] < c_next[3]:  # prev.high < next.low
        return {"top": c_next[3], "bottom": c_prev[2], "mid": (c_next[3] + c_prev[2]) / 2}
    return None


def candles_1h_to_bias_map(candles_1h):
    """Map ts_15m → BULLISH/BEARISH bias dari ema21 1h."""
    closes = [c[4] for c in candles_1h]
    if len(closes) < 21:
        return {}
    ema_vals = ema(closes, 21)
    bias = {}
    for i, c in enumerate(candles_1h):
        bias[c[0]] = "BULLISH" if c[4] > ema_vals[i] else "BEARISH"
    return bias


def find_swing_high_before(candles_15m, idx, lookback=20):
    """Swing high sederhana: max high di N candle sebelum idx."""
    start = max(0, idx - lookback)
    if start >= idx:
        return None
    return max(c[2] for c in candles_15m[start:idx])


def get_1h_bias_for(ts_15m_ms, bias_map):
    """Cari 1h bias yang aktif saat ts_15m_ms (round down ke 1h)."""
    h_ms = (ts_15m_ms // 3_600_000) * 3_600_000
    return bias_map.get(h_ms)


def simulate(candles_1h, candles_15m):
    bias_map = candles_1h_to_bias_map(candles_1h)
    trades = []
    i = 22

    while i < len(candles_15m) - 5:
        c = candles_15m[i]
        ts = c[0]
        # window filter
        hour_utc = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).hour
        if hour_utc not in ACTIVE_HOURS:
            i += 1
            continue

        bias = get_1h_bias_for(ts, bias_map)
        if bias != "BULLISH":  # MVP: long only
            i += 1
            continue

        # Setup A proxy: cari bull FVG di 3 candle sebelum, lalu wait pullback ke FVG
        fvg = None
        fvg_idx = None
        for j in range(i - 3, i):
            f = detect_bull_fvg_at(candles_15m, j)
            if f:
                fvg = f
                fvg_idx = j
                break
        if not fvg:
            i += 1
            continue

        # Pullback: candle current low <= fvg.top dan close > fvg.bottom (rejection)
        if not (c[3] <= fvg["top"] and c[4] > fvg["bottom"]):
            i += 1
            continue
        # Body bullish (close > open) — confirmation
        if c[4] <= c[1]:
            i += 1
            continue

        # SETUP DETECTED → entry di candle next open
        if i + 1 >= len(candles_15m):
            break
        entry = candles_15m[i + 1][1]  # next open
        sl = fvg["bottom"] * (1 - SL_BUFFER_PCT)
        sl_pct = (entry - sl) / entry
        if sl_pct > MAX_SL_PCT or sl_pct <= 0:
            i += 1
            continue

        risk = entry - sl
        tp1_target = find_swing_high_before(candles_15m, i, lookback=20)
        if not tp1_target or tp1_target <= entry:
            tp1_target = entry + risk * RR_MIN
        rr_tp1 = (tp1_target - entry) / risk
        if rr_tp1 < RR_MIN:
            i += 1
            continue
        tp2_target = entry + risk * TP2_RR

        # Simulate forward
        entry_idx = i + 1
        timer_end = entry_idx + TIMER_CANDLES
        result = {
            "ts_open": ts,
            "entry": round(entry, 4),
            "sl": round(sl, 4),
            "tp1": round(tp1_target, 4),
            "tp2": round(tp2_target, 4),
            "rr_tp1": round(rr_tp1, 2),
            "exit_reason": None,
            "exit_price": None,
            "r_multiple": None,
            "tp1_hit": False,
            "be_moved": False,
        }

        sl_active = sl
        for k in range(entry_idx, min(timer_end, len(candles_15m))):
            ck = candles_15m[k]
            # Cek TP1 dulu (more conservative — assume sequential intra-candle)
            if not result["tp1_hit"] and ck[2] >= tp1_target:
                result["tp1_hit"] = True
                result["be_moved"] = True
                sl_active = entry  # move to BE
            # Cek SL after TP1 logic
            if ck[3] <= sl_active:
                # Hit SL atau BE
                if result["tp1_hit"]:
                    # 50% sudah ke-realize di TP1, 50% closed di BE = +0.5R total
                    result["exit_reason"] = "be_after_tp1"
                    result["exit_price"] = sl_active
                    result["r_multiple"] = TP1_PCT * rr_tp1 + (1 - TP1_PCT) * 0
                else:
                    result["exit_reason"] = "sl"
                    result["exit_price"] = sl_active
                    result["r_multiple"] = -1.0
                break
            # Cek TP2
            if result["tp1_hit"] and ck[2] >= tp2_target:
                result["exit_reason"] = "tp2"
                result["exit_price"] = tp2_target
                # 50% TP1 + 30% TP2 + 20% trailing (asumsi BE)
                result["r_multiple"] = (TP1_PCT * rr_tp1 +
                                        TP2_PCT * TP2_RR +
                                        TRAIL_PCT * 0)
                break
        else:
            # Timer expired, exit di close candle terakhir
            if entry_idx + TIMER_CANDLES - 1 < len(candles_15m):
                exit_price = candles_15m[min(timer_end - 1, len(candles_15m) - 1)][4]
                result["exit_reason"] = "timer"
                result["exit_price"] = round(exit_price, 4)
                if result["tp1_hit"]:
                    pl = (exit_price - entry) / risk
                    result["r_multiple"] = TP1_PCT * rr_tp1 + (1 - TP1_PCT) * pl
                else:
                    pl = (exit_price - entry) / risk
                    result["r_multiple"] = pl

        result["r_multiple"] = round(result["r_multiple"] or 0, 3)
        trades.append(result)
        i = timer_end  # skip ahead biar ga overlap

    return trades


def report(trades):
    if not trades:
        print("Tidak ada setup ke-detect dalam range.")
        return
    n = len(trades)
    wins = [t for t in trades if (t["r_multiple"] or 0) > 0]
    losses = [t for t in trades if (t["r_multiple"] or 0) < 0]
    wr = len(wins) / n * 100
    total_r = sum(t["r_multiple"] or 0 for t in trades)
    avg_r = total_r / n

    by_reason = {}
    for t in trades:
        by_reason[t["exit_reason"]] = by_reason.get(t["exit_reason"], 0) + 1

    print(f"\n=== BACKTEST RESULT (Setup A long only, 15m) ===")
    print(f"Trades   : {n}")
    print(f"Win rate : {wr:.1f}%   ({len(wins)}W / {len(losses)}L)")
    print(f"Total R  : {total_r:+.2f}")
    print(f"Avg R    : {avg_r:+.2f}")
    print(f"Exit reasons:")
    for r, c in sorted(by_reason.items(), key=lambda x: -x[1]):
        print(f"  {r:18s} {c}")

    print(f"\n=== Target STRATEGI-15M.md ===")
    print(f"  Win rate target  : 55-65%   {'✓' if 55 <= wr <= 70 else '✗'}")
    print(f"  Avg RR target    : 1:2.2    {'✓' if avg_r >= 0.4 else '✗'} (avg_r=+0.4 ≈ 1:2.2 with 60% WR)")
    print(f"  Expectancy       : {'+' if avg_r > 0 else ''}{avg_r:.2f}R per trade")

    print(f"\n=== Sample trades (first 5) ===")
    for t in trades[:5]:
        ts = datetime.fromtimestamp(t["ts_open"] / 1000, tz=timezone.utc)
        print(f"  {ts.strftime('%Y-%m-%d %H:%M UTC')}  entry={t['entry']:.2f}  "
              f"exit={t['exit_reason']}  R={t['r_multiple']:+.2f}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    pair = sys.argv[1].upper()
    days = int(sys.argv[2])
    source = sys.argv[3] if len(sys.argv) > 3 else "hl"
    hours = days * 24

    print(f"Fetching {pair} 1h + 15m, {days}d back, source={source}...")
    if source == "hl":
        c1h = fetch_hl_candles(pair, "1h", hours)
        c15 = fetch_hl_candles(pair, "15m", hours)
    else:
        sym = f"{pair}/USDT:USDT"
        c1h = fetch_ccxt_candles(sym, "1h", hours)
        c15 = fetch_ccxt_candles(sym, "15m", hours)

    print(f"Got {len(c1h)} × 1h candles, {len(c15)} × 15m candles.")
    if len(c1h) < 30 or len(c15) < 50:
        print("Tidak cukup data.")
        sys.exit(1)

    trades = simulate(c1h, c15)
    report(trades)


if __name__ == "__main__":
    main()
