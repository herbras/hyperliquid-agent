#!/usr/bin/env python3
"""
multi_pair.py — backtest banyak pair × 3 setup × N hari, agregasi.

Loop ke `backtest_15m.py --quiet` untuk tiap pair, kumpulin JSON output,
agregasi pivot table per (pair, setup) → WR + total R + avg R.

Pakai:
  python3 multi_pair.py 30                           # 4 default coin × 3 setup
  python3 multi_pair.py 30 BTC ETH SOL HYPE          # specific pair
  python3 multi_pair.py 14 BTC ETH SOL --source ccxt # via ccxt
"""
import argparse
import json
import os
import subprocess
import sys


DEFAULT_COINS = ["BTC", "ETH", "SOL", "HYPE"]


def run_backtest(pair, days, source):
    script = os.path.join(os.path.dirname(__file__), "backtest_15m.py")
    args = ["python3", script, pair, str(days), source, "--setup", "all", "--quiet"]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            return {"pair": pair, "error": proc.stderr.strip()[:200]}
        return json.loads(proc.stdout.strip().split("\n")[-1])
    except subprocess.TimeoutExpired:
        return {"pair": pair, "error": "timeout 120s"}
    except json.JSONDecodeError as e:
        return {"pair": pair, "error": f"JSON parse: {e}"}


def aggregate(results):
    """Build pivot table: rows=pair, cols=setup, values=(n, WR%, totalR)."""
    pivot = {}  # pair → setup → list of trades
    for r in results:
        if "error" in r:
            continue
        pair = r["pair"]
        pivot[pair] = {"A": [], "B": [], "C": []}
        for t in r["trades"]:
            pivot[pair][t["setup"]].append(t)
    return pivot


def stats(trades):
    if not trades:
        return {"n": 0, "wr": 0, "total_r": 0, "avg_r": 0}
    n = len(trades)
    wins = sum(1 for t in trades if (t["r_multiple"] or 0) > 0)
    total = sum(t["r_multiple"] or 0 for t in trades)
    return {"n": n, "wr": round(wins / n * 100, 1),
            "total_r": round(total, 2), "avg_r": round(total / n, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("days", type=int)
    ap.add_argument("coins", nargs="*", default=DEFAULT_COINS)
    ap.add_argument("--source", default="hl", choices=["hl", "ccxt"])
    args = ap.parse_args()

    print(f"Backtesting {len(args.coins)} pair × 3 setup × {args.days} days "
          f"(source={args.source})...\n", file=sys.stderr)

    results = []
    for coin in args.coins:
        print(f"  → {coin}...", end="", flush=True, file=sys.stderr)
        r = run_backtest(coin, args.days, args.source)
        if "error" in r:
            print(f" ERR: {r['error'][:60]}", file=sys.stderr)
        else:
            print(f" {len(r['trades'])} trades", file=sys.stderr)
        results.append(r)

    pivot = aggregate(results)
    if not pivot:
        print("\nNo results.")
        return

    # === Pivot table ===
    print(f"\n=== PIVOT: pair × setup ({args.days}d) ===\n")
    print(f"{'Pair':<8} {'Setup':<6} {'N':>4} {'WR%':>6} {'totalR':>8} {'avgR':>7}")
    print("-" * 45)
    grand_n = 0
    grand_total_r = 0
    grand_wins = 0
    for pair in sorted(pivot):
        for s in ["A", "B", "C"]:
            st = stats(pivot[pair][s])
            mark = ""
            if st["n"] >= 5:
                if st["wr"] >= 55 and st["avg_r"] >= 0.4:
                    mark = " ✓ HIT TARGET"
                elif st["avg_r"] < 0:
                    mark = " ✗ LOSING"
            print(f"{pair:<8} {s:<6} {st['n']:>4} {st['wr']:>6.1f} "
                  f"{st['total_r']:>+8.2f} {st['avg_r']:>+7.2f}{mark}")
            grand_n += st["n"]
            grand_total_r += st["total_r"]
            grand_wins += int(st["n"] * st["wr"] / 100)
        print()

    # Per-setup totals (across pairs)
    print(f"=== Per-setup totals (across all pair) ===\n")
    print(f"{'Setup':<6} {'N':>4} {'WR%':>6} {'totalR':>8} {'avgR':>7}")
    print("-" * 35)
    for s in ["A", "B", "C"]:
        all_trades = []
        for pair in pivot:
            all_trades.extend(pivot[pair][s])
        st = stats(all_trades)
        verdict = ""
        if st["n"] >= 10:
            if st["wr"] >= 55 and st["avg_r"] >= 0.4:
                verdict = " → KEEP (per STRATEGI-15M.md target)"
            elif st["wr"] < 45 or st["avg_r"] < 0:
                verdict = " → SKIP/REVIEW (di luar target)"
            else:
                verdict = " → MARGINAL"
        print(f"{s:<6} {st['n']:>4} {st['wr']:>6.1f} "
              f"{st['total_r']:>+8.2f} {st['avg_r']:>+7.2f}{verdict}")

    grand_wr = grand_wins / grand_n * 100 if grand_n else 0
    print(f"\n=== Grand total ===")
    print(f"  n={grand_n}  WR={grand_wr:.1f}%  total={grand_total_r:+.2f}R  "
          f"avg={grand_total_r/grand_n:+.2f}R" if grand_n else "  no trades")


if __name__ == "__main__":
    main()
