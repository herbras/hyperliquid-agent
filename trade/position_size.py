#!/usr/bin/env python3
"""
position_size.py — hitung qty trade dari risk per trade.

Formula: risk_amount = account_balance × risk_pct
        qty = risk_amount / (entry - sl)         [untuk long]
        qty = risk_amount / (sl - entry)         [untuk short]

Pakai:
  python3 position_size.py --pair BTCUSDT --entry 67380 --sl 67110 --side long
  python3 position_size.py --pair BTCUSDT --entry 67380 --sl 67110 --side long --balance 1000
  python3 position_size.py --pair BTCUSDT --entry 67380 --sl 67110 --side long --risk 0.5

Env (untuk auto-fetch balance dari Bybit):
  BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_ENV (mainnet|testnet)

Default risk: 1% (per STRATEGI-15M.md "be wide" range 0.5-1%).
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request


BYBIT_BASE = {
    "mainnet": "https://api.bybit.com",
    "testnet": "https://api-testnet.bybit.com",
}.get(os.getenv("BYBIT_ENV", "mainnet"), "https://api.bybit.com")


def sign_request(params_str, secret, timestamp, api_key, recv_window=5000):
    """V5 HMAC: signature = HMAC_SHA256(timestamp + api_key + recv_window + params)"""
    payload = f"{timestamp}{api_key}{recv_window}{params_str}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def get_balance_usdt():
    """Fetch UNIFIED account USDT balance dari Bybit V5."""
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    if not (api_key and api_secret):
        raise RuntimeError("BYBIT_API_KEY/SECRET tidak set — pakai --balance manual")

    ts = str(int(time.time() * 1000))
    qs = "accountType=UNIFIED"
    sig = sign_request(qs, api_secret, ts, api_key)
    url = f"{BYBIT_BASE}/v5/account/wallet-balance?{qs}"

    req = urllib.request.Request(url, headers={
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-SIGN": sig,
        "X-BAPI-TIMESTAMP": ts,
        "X-BAPI-RECV-WINDOW": "5000",
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        body = json.loads(r.read())
    if body.get("retCode") != 0:
        raise RuntimeError(f"Bybit API: {body.get('retCode')} {body.get('retMsg')}")

    accounts = body["result"]["list"]
    if not accounts:
        raise RuntimeError("No UNIFIED account found")
    coins = accounts[0].get("coin", [])
    for c in coins:
        if c["coin"] == "USDT":
            return float(c.get("walletBalance", 0))
    return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True, help="BTCUSDT, ETHUSDT, dst")
    ap.add_argument("--entry", type=float, required=True, help="entry price")
    ap.add_argument("--sl", type=float, required=True, help="stop loss price")
    ap.add_argument("--side", choices=["long", "short"], required=True)
    ap.add_argument("--balance", type=float, default=None,
                    help="account balance USDT (default: fetch dari Bybit)")
    ap.add_argument("--risk", type=float, default=1.0,
                    help="risk per trade %% (default 1.0, range 0.5-1.0 per STRATEGI-15M.md)")
    ap.add_argument("--leverage", type=int, default=10,
                    help="leverage untuk display margin requirement (default 10x)")
    args = ap.parse_args()

    if args.risk > 2.0:
        print(f"⚠ WARNING: risk {args.risk}% di atas 2% — di luar range 'be wide'.",
              file=sys.stderr)

    # Validate SL position
    if args.side == "long" and args.sl >= args.entry:
        print(f"ERROR: untuk long, SL ({args.sl}) harus DI BAWAH entry ({args.entry})",
              file=sys.stderr)
        sys.exit(2)
    if args.side == "short" and args.sl <= args.entry:
        print(f"ERROR: untuk short, SL ({args.sl}) harus DI ATAS entry ({args.entry})",
              file=sys.stderr)
        sys.exit(2)

    # Get balance
    if args.balance is None:
        try:
            balance = get_balance_usdt()
            print(f"Account balance: {balance:.2f} USDT (fetched from Bybit)",
                  file=sys.stderr)
        except Exception as e:
            print(f"ERROR fetching balance: {e}", file=sys.stderr)
            print("Pakai --balance untuk override manual.", file=sys.stderr)
            sys.exit(2)
    else:
        balance = args.balance

    # Compute
    risk_amount = balance * args.risk / 100
    sl_distance = abs(args.entry - args.sl)
    sl_pct = sl_distance / args.entry * 100
    qty = risk_amount / sl_distance
    notional = qty * args.entry
    margin = notional / args.leverage

    # Sanity checks per STRATEGI-15M.md
    warnings = []
    if sl_pct > 1.5:
        warnings.append(f"SL distance {sl_pct:.2f}% > 1.5% — terlalu lebar bahkan untuk 15m. SKIP.")
    if sl_pct > 1.0:
        warnings.append(f"SL distance {sl_pct:.2f}% > 1%. Borderline — pastikan setup A confluence kuat.")
    if margin > balance * 0.5:
        warnings.append(f"Margin {margin:.2f} > 50% balance — over-leveraged.")

    print(f"\n=== POSITION SIZE — {args.pair} {args.side.upper()} ===")
    print(f"Balance     : {balance:>12.2f} USDT")
    print(f"Risk        : {args.risk:>11.2f}%   = {risk_amount:.2f} USDT")
    print(f"Entry       : {args.entry:>12.4f}")
    print(f"SL          : {args.sl:>12.4f}      ({sl_pct:.2f}% dari entry)")
    print(f"SL distance : {sl_distance:>12.4f}")
    print(f"---")
    print(f"Qty         : {qty:>12.4f} {args.pair.replace('USDT','').replace('USDC','')}")
    print(f"Notional    : {notional:>12.2f} USDT")
    print(f"Margin (×{args.leverage}): {margin:>12.2f} USDT  ({margin/balance*100:.1f}% of balance)")

    if warnings:
        print(f"\n⚠ WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
        if any("SKIP" in w for w in warnings):
            sys.exit(1)

    # Output JSON di line terakhir untuk parsing programmatic
    print(f"\n{json.dumps({'qty': round(qty, 4), 'notional': round(notional, 2), 'margin': round(margin, 2), 'sl_pct': round(sl_pct, 3), 'risk_amount': round(risk_amount, 2)})}")


if __name__ == "__main__":
    main()
