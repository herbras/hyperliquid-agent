#!/usr/bin/env python3
"""
backtest_15m.py — backtest 3 setup di 15m strategi (Setup A/B/C, long only).

MVP detection (simplified dari full SMC):
  Setup A — bias 1h bullish + bull FVG di 3 candle terakhir +
            pullback into FVG + bullish body close (continuation)
  Setup B — bias 1h bearish (counter-trend) + close above prior swing high
            (CHoCH) + bull FVG within 0.5% of close (reversal)
  Setup C — EQL detected (2+ lows within 0.2%) + sweep below + close back
            above EQL with bullish body (liquidity grab)

Limitasi MVP:
- Long only
- FVG sebagai proxy OB (lebih mudah detect dari raw candle)
- Macro bias 1h via ema21 (proxy Swing BOS)
- Tidak account slippage / fees / funding cost
- Window filter: 00-04 + 13-17 UTC

Usage:
  python3 backtest_15m.py BTC 30                  # all setups
  python3 backtest_15m.py BTC 30 --setup A        # Setup A only
  python3 backtest_15m.py BTC 30 --setup B,C      # B & C
  python3 backtest_15m.py SOL 14 ccxt --setup all # specific source
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone


# === Config — match STRATEGI-15M.md ===
SL_BUFFER_PCT = 0.004
MAX_SL_PCT = 0.015
RR_MIN = 2.0
TP2_RR = 4.0
TIMER_CANDLES = 12        # 12 × 15m = 3 jam
TP1_PCT = 0.5
TP2_PCT = 0.3
TRAIL_PCT = 0.2
ACTIVE_HOURS = set(range(0, 4)) | set(range(13, 17))


# ── Data fetch (HL native + ccxt fallback) ───────────────────────────
def fetch_hl_candles(coin, interval, hours_back):
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


def fetch_ccxt_candles(symbol, interval, hours_back):
    import ccxt
    ex_id = os.getenv("BACKTEST_EXCHANGE", "htx")
    ex = getattr(ccxt, ex_id)({"enableRateLimit": True})
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


# ── Helpers ──────────────────────────────────────────────────────────
def ema(values, period):
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def candles_1h_to_bias_map(candles_1h):
    closes = [c[4] for c in candles_1h]
    if len(closes) < 21:
        return {}
    ema_vals = ema(closes, 21)
    return {c[0]: ("BULLISH" if c[4] > ema_vals[i] else "BEARISH")
            for i, c in enumerate(candles_1h)}


def get_1h_bias_for(ts_15m_ms, bias_map):
    h_ms = (ts_15m_ms // 3_600_000) * 3_600_000
    return bias_map.get(h_ms)


def detect_bull_fvg_at(candles, i):
    if i < 1 or i >= len(candles) - 1:
        return None
    c_prev, c_next = candles[i - 1], candles[i + 1]
    if c_prev[2] < c_next[3]:
        return {"top": c_next[3], "bottom": c_prev[2],
                "mid": (c_next[3] + c_prev[2]) / 2, "idx": i}
    return None


def find_swing_high_before(candles, idx, lookback=20):
    start = max(0, idx - lookback)
    if start >= idx:
        return None
    return max(c[2] for c in candles[start:idx])


def find_swing_low_before(candles, idx, lookback=20):
    start = max(0, idx - lookback)
    if start >= idx:
        return None
    return min(c[3] for c in candles[start:idx])


def find_recent_eql(candles, idx, lookback=15, tolerance_pct=0.002):
    """Cari 2+ swing low yang dekat (within tolerance) dalam lookback candle."""
    start = max(0, idx - lookback)
    lows = [(j, candles[j][3]) for j in range(start, idx)]
    if len(lows) < 5:
        return None
    # Find local lows (lower than 2 neighbors)
    locals_ = [(j, l) for k, (j, l) in enumerate(lows[1:-1], 1)
               if l < lows[k - 1][1] and l < lows[k + 1][1]]
    if len(locals_) < 2:
        return None
    # Pair-wise check tolerance
    for a in range(len(locals_)):
        for b in range(a + 1, len(locals_)):
            ja, la = locals_[a]
            jb, lb = locals_[b]
            avg = (la + lb) / 2
            if abs(la - lb) / avg <= tolerance_pct:
                return {"level": min(la, lb), "idxs": (ja, jb)}
    return None


# ── Setup detectors — return entry_params dict or None ───────────────

def detect_setup_a(candles_15m, i, bias_1h):
    """Continuation: 1h bullish + bull FVG + pullback + bullish body."""
    if bias_1h != "BULLISH":
        return None
    fvg = None
    for j in range(max(0, i - 3), i):
        f = detect_bull_fvg_at(candles_15m, j)
        if f:
            fvg = f
            break
    if not fvg:
        return None
    c = candles_15m[i]
    if not (c[3] <= fvg["top"] and c[4] > fvg["bottom"]):
        return None
    if c[4] <= c[1]:  # need bullish body
        return None
    sl = fvg["bottom"] * (1 - SL_BUFFER_PCT)
    return {"setup": "A", "fvg": fvg, "sl": sl,
            "tp1_target": find_swing_high_before(candles_15m, i, 20)}


def detect_setup_b(candles_15m, i, bias_1h):
    """Reversal: 1h bearish (counter-trend) + CHoCH + bull FVG nearby."""
    if bias_1h != "BEARISH":
        return None
    c = candles_15m[i]
    # CHoCH: close above prior swing high
    swing_high = find_swing_high_before(candles_15m, i, lookback=10)
    if not swing_high or c[4] <= swing_high:
        return None
    # Bull FVG harus ada within last 5 candle
    fvg = None
    for j in range(max(0, i - 5), i):
        f = detect_bull_fvg_at(candles_15m, j)
        if f and abs(c[4] - f["mid"]) / c[4] <= 0.005:  # within 0.5%
            fvg = f
            break
    if not fvg:
        return None
    if c[4] <= c[1]:  # need bullish body
        return None
    sl = fvg["bottom"] * (1 - SL_BUFFER_PCT)
    return {"setup": "B", "fvg": fvg, "sl": sl,
            "tp1_target": swing_high + (swing_high - sl) * 0.3}  # extension target


def detect_setup_c(candles_15m, i, bias_1h):
    """Sweep: 1h bullish + EQL sweep + close back above with bullish body."""
    if bias_1h != "BULLISH":
        return None
    eql = find_recent_eql(candles_15m, i, lookback=15)
    if not eql:
        return None
    c = candles_15m[i]
    # Sweep: candle low went BELOW EQL level
    if c[3] >= eql["level"]:
        return None
    # Recovery: close BACK above EQL
    if c[4] <= eql["level"]:
        return None
    # Bullish body, body > 60% range (per playbook Setup C)
    body = c[4] - c[1]
    rng = c[2] - c[3]
    if rng <= 0 or body / rng < 0.6 or body <= 0:
        return None
    # SL below sweep wick
    sl = c[3] * (1 - SL_BUFFER_PCT)
    return {"setup": "C", "level": eql["level"], "sl": sl,
            "tp1_target": find_swing_high_before(candles_15m, i, 15)}


SETUP_DETECTORS = {"A": detect_setup_a, "B": detect_setup_b, "C": detect_setup_c}


# ── Forward simulation (reusable per setup) ──────────────────────────
def simulate_forward(candles_15m, entry_idx, entry, sl, tp1_target):
    risk = entry - sl
    if risk <= 0:
        return None
    rr_tp1 = (tp1_target - entry) / risk if tp1_target else 0
    if rr_tp1 < RR_MIN:
        # Force tp1 ke RR_MIN minimum
        tp1_target = entry + risk * RR_MIN
        rr_tp1 = RR_MIN
    tp2_target = entry + risk * TP2_RR
    timer_end = entry_idx + TIMER_CANDLES

    result = {"entry": round(entry, 4), "sl": round(sl, 4),
              "tp1": round(tp1_target, 4), "tp2": round(tp2_target, 4),
              "rr_tp1": round(rr_tp1, 2),
              "exit_reason": None, "r_multiple": None, "tp1_hit": False}

    sl_active = sl
    for k in range(entry_idx, min(timer_end, len(candles_15m))):
        ck = candles_15m[k]
        if not result["tp1_hit"] and ck[2] >= tp1_target:
            result["tp1_hit"] = True
            sl_active = entry  # BE
        if ck[3] <= sl_active:
            if result["tp1_hit"]:
                result["exit_reason"] = "be_after_tp1"
                result["r_multiple"] = TP1_PCT * rr_tp1
            else:
                result["exit_reason"] = "sl"
                result["r_multiple"] = -1.0
            return result
        if result["tp1_hit"] and ck[2] >= tp2_target:
            result["exit_reason"] = "tp2"
            result["r_multiple"] = (TP1_PCT * rr_tp1 + TP2_PCT * TP2_RR
                                    + TRAIL_PCT * 0)
            return result

    # Timer expired
    last_idx = min(timer_end - 1, len(candles_15m) - 1)
    exit_price = candles_15m[last_idx][4]
    pl = (exit_price - entry) / risk
    result["exit_reason"] = "timer"
    if result["tp1_hit"]:
        result["r_multiple"] = TP1_PCT * rr_tp1 + (1 - TP1_PCT) * pl
    else:
        result["r_multiple"] = pl
    return result


# ── Main simulate (loop candle, dispatch ke setup detectors) ─────────
def simulate(candles_1h, candles_15m, setups):
    bias_map = candles_1h_to_bias_map(candles_1h)
    trades = []
    i = 22

    while i < len(candles_15m) - TIMER_CANDLES - 1:
        c = candles_15m[i]
        ts = c[0]
        hour_utc = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).hour
        if hour_utc not in ACTIVE_HOURS:
            i += 1
            continue

        bias = get_1h_bias_for(ts, bias_map)

        # Try setup detectors in order — first match wins (priority A > B > C)
        match = None
        for s in setups:
            params = SETUP_DETECTORS[s](candles_15m, i, bias)
            if params:
                match = params
                break

        if not match:
            i += 1
            continue

        entry = candles_15m[i + 1][1]  # next open
        sl_pct = (entry - match["sl"]) / entry
        if sl_pct > MAX_SL_PCT or sl_pct <= 0:
            i += 1
            continue

        result = simulate_forward(candles_15m, i + 1, entry, match["sl"],
                                   match["tp1_target"] or entry + (entry - match["sl"]) * RR_MIN)
        if not result:
            i += 1
            continue

        result["setup"] = match["setup"]
        result["ts_open"] = ts
        result["r_multiple"] = round(result["r_multiple"] or 0, 3)
        trades.append(result)
        i += TIMER_CANDLES  # skip ahead supaya ga overlap

    return trades


# ── Report ───────────────────────────────────────────────────────────
def report_setup(setup, trades):
    if not trades:
        print(f"  Setup {setup}: 0 trades")
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
    print(f"  Setup {setup}: n={n:>3}  WR={wr:>5.1f}%  ({len(wins)}W/{len(losses)}L)  "
          f"total={total_r:+6.2f}R  avg={avg_r:+5.2f}R  exits={by_reason}")


def report(trades):
    if not trades:
        print("Tidak ada setup ke-detect.")
        return
    print(f"\n=== BACKTEST RESULT (15m, long only) ===\n")
    print(f"Total trades  : {len(trades)}")
    wins = [t for t in trades if (t["r_multiple"] or 0) > 0]
    wr = len(wins) / len(trades) * 100
    total_r = sum(t["r_multiple"] or 0 for t in trades)
    print(f"Overall WR    : {wr:.1f}%   total: {total_r:+.2f}R   avg: {total_r/len(trades):+.2f}R\n")
    print(f"Per setup:")
    for s in ["A", "B", "C"]:
        s_trades = [t for t in trades if t["setup"] == s]
        report_setup(s, s_trades)
    print(f"\n=== STRATEGI-15M.md target ===")
    print(f"  WR target    : 55-65%   {'✓' if 55 <= wr <= 70 else '✗'}")
    print(f"  Avg R target : +0.4     {'✓' if total_r/len(trades) >= 0.4 else '✗'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pair", help="BTC, ETH, SOL atau pair format ccxt seperti BTC/USDT")
    ap.add_argument("days", type=int)
    ap.add_argument("source", nargs="?", default="hl",
                    choices=["hl", "ccxt"], help="data source (default hl)")
    ap.add_argument("--setup", default="all",
                    help="A | B | C | A,B | all (default: all)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.setup == "all":
        setups = ["A", "B", "C"]
    else:
        setups = [s.strip().upper() for s in args.setup.split(",")]
    for s in setups:
        if s not in SETUP_DETECTORS:
            print(f"ERROR: setup '{s}' tidak dikenal", file=sys.stderr)
            sys.exit(2)

    hours = args.days * 24
    if not args.quiet:
        print(f"Fetching {args.pair} 1h + 15m, {args.days}d back, source={args.source}, setups={setups}",
              file=sys.stderr)

    if args.source == "hl":
        c1h = fetch_hl_candles(args.pair, "1h", hours)
        c15 = fetch_hl_candles(args.pair, "15m", hours)
    else:
        sym = args.pair if "/" in args.pair else f"{args.pair}/USDT"
        c1h = fetch_ccxt_candles(sym, "1h", hours)
        c15 = fetch_ccxt_candles(sym, "15m", hours)

    if not args.quiet:
        print(f"Got {len(c1h)} × 1h, {len(c15)} × 15m candles", file=sys.stderr)
    if len(c1h) < 30 or len(c15) < 50:
        print("Tidak cukup data.", file=sys.stderr)
        sys.exit(1)

    trades = simulate(c1h, c15, setups)
    if args.quiet:
        # JSON output untuk multi_pair aggregator
        print(json.dumps({"pair": args.pair, "days": args.days, "setups": setups,
                          "trades": trades}))
    else:
        report(trades)


if __name__ == "__main__":
    main()
