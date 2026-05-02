#!/usr/bin/env python3
"""
bybit_execute.py — minimal Bybit V5 execution wrapper untuk sniper.

DEFAULT DRY-RUN. Order real harus explicit `BYBIT_DRY_RUN=0` + `--confirm`.

Pakai:
  # Cek balance + permissions (read-only, safe)
  python3 bybit_execute.py preflight

  # Place limit order DRY-RUN (default — print payload, don't send)
  python3 bybit_execute.py place \\
    --pair BTCUSDT --side long --qty 0.01 \\
    --entry 67380 --sl 67110 --tp1 67980 --tp2 68450

  # Place real (HARUS explicit dua-duanya)
  BYBIT_DRY_RUN=0 python3 bybit_execute.py place ... --confirm

  # Get position
  python3 bybit_execute.py position --pair BTCUSDT

  # Cancel all open orders
  python3 bybit_execute.py cancel-all --pair BTCUSDT

Env wajib (read mode):
  BYBIT_API_KEY, BYBIT_API_SECRET
  BYBIT_ENV       (mainnet | testnet, default mainnet)
  BYBIT_DRY_RUN   (default "1" — set "0" untuk real order)

Untuk eksekusi natural-language yang lebih lengkap, install official skill:
  https://github.com/bybit-exchange/skills
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request


BYBIT_BASE = {
    "mainnet": "https://api.bybit.com",
    "testnet": "https://api-testnet.bybit.com",
}.get(os.getenv("BYBIT_ENV", "mainnet"), "https://api.bybit.com")

DRY_RUN = os.getenv("BYBIT_DRY_RUN", "1") != "0"
RECV_WINDOW = "5000"


def get_creds():
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    if not (api_key and api_secret):
        print("ERROR: BYBIT_API_KEY dan BYBIT_API_SECRET wajib di-set.", file=sys.stderr)
        print("Lihat: https://github.com/bybit-exchange/skills (untuk RSA support)",
              file=sys.stderr)
        sys.exit(2)
    return api_key, api_secret


def sign(payload_str, secret, ts, api_key):
    base = f"{ts}{api_key}{RECV_WINDOW}{payload_str}"
    return hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()


def request(method, path, params=None, body=None):
    """Signed request. params untuk GET, body untuk POST."""
    api_key, api_secret = get_creds()
    ts = str(int(time.time() * 1000))

    if method == "GET":
        qs = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        sig = sign(qs, api_secret, ts, api_key)
        url = f"{BYBIT_BASE}{path}" + (f"?{qs}" if qs else "")
        req = urllib.request.Request(url, headers={
            "X-BAPI-API-KEY": api_key,
            "X-BAPI-SIGN": sig,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": RECV_WINDOW,
        })
    else:  # POST
        body_str = json.dumps(body or {}, separators=(",", ":"))
        sig = sign(body_str, api_secret, ts, api_key)
        url = f"{BYBIT_BASE}{path}"
        req = urllib.request.Request(url, data=body_str.encode(), headers={
            "X-BAPI-API-KEY": api_key,
            "X-BAPI-SIGN": sig,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": RECV_WINDOW,
            "Content-Type": "application/json",
        })

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return {"retCode": -1, "retMsg": f"HTTP {e.code}: {body}"}


# === Commands ===

def cmd_preflight(args):
    """Read-only safety check sebelum execution."""
    print(f"=== Bybit Preflight ({BYBIT_ENV_LABEL}) ===")

    # 1. Server time
    try:
        with urllib.request.urlopen(f"{BYBIT_BASE}/v5/market/time", timeout=5) as r:
            srv = json.loads(r.read())
        srv_ts = int(srv["result"]["timeSecond"])
        local_ts = int(time.time())
        delta = abs(srv_ts - local_ts)
        status = "✓" if delta < 5 else "✗"
        print(f"{status} Clock sync   : delta {delta}s {'(>5s = signature akan gagal!)' if delta >= 5 else ''}")
        if delta >= 5:
            sys.exit(1)
    except Exception as e:
        print(f"✗ Clock check  : {e}")
        sys.exit(1)

    # 2. API key validity + balance
    res = request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
    if res.get("retCode") != 0:
        print(f"✗ API key      : {res.get('retCode')} {res.get('retMsg')}")
        if res.get("retCode") == 10003:
            print("  → Signature error. Cek BYBIT_API_SECRET.")
        elif res.get("retCode") == 10010:
            print("  → IP not whitelisted. Tambah IP di Bybit API Management.")
        elif res.get("retCode") == 10005:
            print("  → Insufficient permissions. Cek API key permissions.")
        sys.exit(1)

    balance = 0.0
    for c in res["result"]["list"][0].get("coin", []):
        if c["coin"] == "USDT":
            balance = float(c.get("walletBalance", 0))
            break
    print(f"✓ API key      : valid")
    print(f"✓ Balance      : {balance:.2f} USDT (UNIFIED)")

    # 3. API key permissions check
    res = request("GET", "/v5/user/query-api", {})
    if res.get("retCode") == 0:
        info = res["result"]
        perms = info.get("permissions", {})
        has_withdraw = bool(perms.get("Wallet", []))
        if has_withdraw:
            print(f"✗ Permissions  : Wallet/Withdraw ENABLED — UNSAFE!")
            print(f"  → Buat key baru tanpa Withdraw permission. STOP execution.")
            sys.exit(1)
        else:
            print(f"✓ Permissions  : no Withdraw (safe)")
        is_master = info.get("isMaster", True)
        if is_master:
            print(f"⚠ Account      : MASTER account — recommended pakai SUB-account untuk AI trading")
        else:
            print(f"✓ Account      : sub-account (recommended)")
    else:
        print(f"⚠ Permissions  : {res.get('retMsg')} (non-blocking)")

    print(f"\n=== Status ===")
    print(f"DRY_RUN        : {'YES (default)' if DRY_RUN else 'NO — WILL SEND REAL ORDERS'}")
    print(f"BYBIT_ENV      : {os.getenv('BYBIT_ENV', 'mainnet')}")
    print(f"\nReady. Run `place` command untuk place order.")


def cmd_place(args):
    """Place limit order dengan SL + TP attached. DRY_RUN default."""
    # Validate
    if args.side not in ("long", "short"):
        print("side harus long|short", file=sys.stderr); sys.exit(2)
    if args.side == "long" and args.sl >= args.entry:
        print(f"ERROR: long SL ({args.sl}) harus < entry ({args.entry})", file=sys.stderr)
        sys.exit(2)
    if args.side == "short" and args.sl <= args.entry:
        print(f"ERROR: short SL ({args.sl}) harus > entry ({args.entry})", file=sys.stderr)
        sys.exit(2)

    side_bybit = "Buy" if args.side == "long" else "Sell"
    body = {
        "category": "linear",
        "symbol": args.pair,
        "side": side_bybit,
        "orderType": "Limit",
        "qty": str(args.qty),
        "price": str(args.entry),
        "timeInForce": "GTC",
        "stopLoss": str(args.sl),
        "slOrderType": "Market",
        "slTriggerBy": "LastPrice",
        "takeProfit": str(args.tp1),
        "tpOrderType": "Limit",
        "tpLimitPrice": str(args.tp1),
        "tpTriggerBy": "LastPrice",
        "tpslMode": "Partial",   # partial TP biar bisa staged TP1/TP2
        "reduceOnly": False,
        "positionIdx": 0,         # one-way mode
    }

    print(f"=== PLACE ORDER {'(DRY-RUN — tidak dikirim)' if DRY_RUN else '(REAL)'} ===")
    print(json.dumps(body, indent=2))

    if DRY_RUN:
        print(f"\n→ DRY_RUN aktif (BYBIT_DRY_RUN={os.getenv('BYBIT_DRY_RUN','1')}).")
        print(f"→ Untuk real: BYBIT_DRY_RUN=0 ... --confirm")
        return

    if not args.confirm:
        print(f"\n→ ERROR: real order butuh --confirm flag.", file=sys.stderr)
        sys.exit(2)

    print(f"\n→ Sending real order to {BYBIT_BASE}...")
    res = request("POST", "/v5/order/create", body=body)
    if res.get("retCode") == 0:
        order_id = res["result"]["orderId"]
        print(f"✓ Order placed: {order_id}")
        if args.tp2:
            print(f"  Note: TP2 ({args.tp2}) belum di-place. Place manual setelah TP1 hit,")
            print(f"        atau pakai conditional order terpisah.")
    else:
        print(f"✗ FAILED: {res.get('retCode')} {res.get('retMsg')}")
        sys.exit(1)


def cmd_position(args):
    res = request("GET", "/v5/position/list",
                  {"category": "linear", "symbol": args.pair})
    if res.get("retCode") != 0:
        print(f"ERROR: {res.get('retCode')} {res.get('retMsg')}", file=sys.stderr)
        sys.exit(1)
    positions = res["result"]["list"]
    active = [p for p in positions if float(p.get("size", 0)) > 0]
    if not active:
        print(f"No active position for {args.pair}.")
        return
    for p in active:
        print(f"=== {p['symbol']} {p['side'].upper()} ===")
        print(f"  Size       : {p['size']}")
        print(f"  Avg entry  : {p['avgPrice']}")
        print(f"  Mark price : {p.get('markPrice', 'n/a')}")
        print(f"  Unrealized : {p.get('unrealisedPnl', 'n/a')} USDT")
        print(f"  SL         : {p.get('stopLoss', 'none')}")
        print(f"  TP         : {p.get('takeProfit', 'none')}")


def cmd_cancel_all(args):
    print(f"=== CANCEL ALL {args.pair} {'(DRY-RUN)' if DRY_RUN else '(REAL)'} ===")
    if DRY_RUN:
        print("DRY_RUN aktif — no orders cancelled.")
        return
    if not args.confirm:
        print("ERROR: butuh --confirm", file=sys.stderr); sys.exit(2)
    res = request("POST", "/v5/order/cancel-all",
                  body={"category": "linear", "symbol": args.pair})
    if res.get("retCode") == 0:
        cancelled = res["result"].get("list", [])
        print(f"✓ Cancelled {len(cancelled)} orders")
    else:
        print(f"✗ {res.get('retMsg')}", file=sys.stderr); sys.exit(1)


BYBIT_ENV_LABEL = os.getenv("BYBIT_ENV", "mainnet").upper()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("preflight")

    p_place = sub.add_parser("place")
    p_place.add_argument("--pair", required=True)
    p_place.add_argument("--side", choices=["long", "short"], required=True)
    p_place.add_argument("--qty", type=float, required=True)
    p_place.add_argument("--entry", type=float, required=True)
    p_place.add_argument("--sl", type=float, required=True)
    p_place.add_argument("--tp1", type=float, required=True)
    p_place.add_argument("--tp2", type=float, default=None)
    p_place.add_argument("--confirm", action="store_true",
                         help="explicit confirm untuk real order")

    p_pos = sub.add_parser("position")
    p_pos.add_argument("--pair", required=True)

    p_cancel = sub.add_parser("cancel-all")
    p_cancel.add_argument("--pair", required=True)
    p_cancel.add_argument("--confirm", action="store_true")

    args = ap.parse_args()

    handlers = {
        "preflight": cmd_preflight,
        "place": cmd_place,
        "position": cmd_position,
        "cancel-all": cmd_cancel_all,
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
