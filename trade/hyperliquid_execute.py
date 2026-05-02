#!/usr/bin/env python3
"""
hyperliquid_execute.py — HL execution wrapper untuk sniper.

DEFAULT DRY-RUN. Order real butuh `HL_DRY_RUN=0` + `--confirm`.

Setup workflow (sekali):
  1. app.hyperliquid.xyz → Settings → API → "Authorize API Wallet"
  2. Generate agent keypair lokal (eth_account.Account.create())
  3. Sign authorization via main wallet (Ledger/MetaMask)
  4. Save agent private key, set di .env:
       HYPERLIQUID_ACCOUNT_ADDRESS=0xMainWalletAddress    # public, funded
       HYPERLIQUID_AGENT_KEY=0xAgentPrivateKey             # signing only

Pakai:
  python3 hyperliquid_execute.py preflight
  python3 hyperliquid_execute.py place --coin BTC --side long --qty 0.01 \\
    --entry 67380 --sl 67110 --tp1 67980
  HL_DRY_RUN=0 python3 hyperliquid_execute.py place ... --confirm
  python3 hyperliquid_execute.py position --coin BTC
  python3 hyperliquid_execute.py cancel-all --coin BTC --confirm

Env:
  HYPERLIQUID_API_URL          default https://api.hyperliquid.xyz
  HYPERLIQUID_ACCOUNT_ADDRESS  main wallet address (public)
  HYPERLIQUID_AGENT_KEY        agent wallet private key (signing only)
  HL_DRY_RUN                   default "1"; set "0" untuk real order
  HL_BALANCE_CAP               warn kalau main wallet > $X (default 1000)
"""
import argparse
import json
import os
import sys

try:
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from eth_account import Account
except ImportError:
    print("ERROR: pip install --user --break-system-packages "
          "hyperliquid-python-sdk eth-account", file=sys.stderr)
    sys.exit(1)


API_URL = os.getenv("HYPERLIQUID_API_URL", "https://api.hyperliquid.xyz")
DRY_RUN = os.getenv("HL_DRY_RUN", "1") != "0"
BALANCE_CAP = float(os.getenv("HL_BALANCE_CAP", "1000"))


def get_creds():
    addr = os.getenv("HYPERLIQUID_ACCOUNT_ADDRESS")
    key = os.getenv("HYPERLIQUID_AGENT_KEY")
    if not addr or not key:
        print("ERROR: HYPERLIQUID_ACCOUNT_ADDRESS + HYPERLIQUID_AGENT_KEY wajib di-set",
              file=sys.stderr)
        print("Setup: app.hyperliquid.xyz → Settings → API → Authorize API Wallet",
              file=sys.stderr)
        sys.exit(2)
    if not addr.startswith("0x") or len(addr) != 42:
        print(f"ERROR: ACCOUNT_ADDRESS format salah ({addr[:10]}...). Harus 0x + 40 hex.",
              file=sys.stderr)
        sys.exit(2)
    return addr, key


def get_clients():
    addr, key = get_creds()
    account = Account.from_key(key)
    info = Info(API_URL, skip_ws=True)
    exchange = Exchange(account, API_URL, account_address=addr)
    return info, exchange, addr, account.address


def cmd_preflight(args):
    print(f"=== HL Preflight ({API_URL}) ===")
    info, exchange, main_addr, agent_addr = get_clients()

    # Critical safety: agent address HARUS beda dari main address.
    # Kalau sama → user pakai MAIN wallet private key (BAHAYA).
    if main_addr.lower() == agent_addr.lower():
        print(f"✗ FATAL: agent_key derive ke address SAMA dengan main address.")
        print(f"  Itu berarti HYPERLIQUID_AGENT_KEY adalah private key MAIN wallet.")
        print(f"  → STOP. Revoke wallet itu (USDC pindah ke wallet baru),")
        print(f"    lalu buat AGENT wallet di app.hyperliquid.xyz")
        sys.exit(1)

    print(f"✓ Main wallet : {main_addr}")
    print(f"✓ Agent addr  : {agent_addr}  (signing only, no funds)")

    # Fetch main user state
    try:
        state = info.user_state(main_addr)
    except Exception as e:
        print(f"✗ Gagal fetch user_state: {e}")
        sys.exit(1)

    margin = state.get("marginSummary", {})
    balance = float(margin.get("accountValue", 0))
    used = float(margin.get("totalMarginUsed", 0))
    free = balance - used
    print(f"✓ Account     : ${balance:.2f} USDC  (free: ${free:.2f}, margin used: ${used:.2f})")

    # Open positions
    positions = state.get("assetPositions", [])
    active = [p for p in positions if float(p["position"]["szi"]) != 0]
    print(f"✓ Positions   : {len(active)} active")
    for p in active:
        pos = p["position"]
        side = "LONG" if float(pos["szi"]) > 0 else "SHORT"
        print(f"   {pos['coin']:6s} {side:5s} size={pos['szi']:>10s}  entry={pos['entryPx']}")

    # Open orders
    try:
        orders = info.open_orders(main_addr)
        print(f"✓ Open orders : {len(orders)}")
    except Exception:
        pass

    print(f"\n=== Status ===")
    print(f"DRY_RUN     : {'YES (default)' if DRY_RUN else 'NO — WILL SEND REAL ORDERS'}")
    print(f"Balance cap : ${BALANCE_CAP:.0f}")

    if balance > BALANCE_CAP:
        print(f"\n⚠ WARNING: balance ${balance:.2f} > cap ${BALANCE_CAP:.0f}")
        print(f"  Recommend: pakai sub-account / pisah wallet untuk AI trading,")
        print(f"             biar exposure terbatas kalau ada bug.")

    print(f"\n→ Ready. Run `place` untuk place order (DRY_RUN dulu).")


def cmd_place(args):
    if args.side not in ("long", "short"):
        print("side harus long|short", file=sys.stderr); sys.exit(2)

    is_buy = args.side == "long"

    # Validate SL position
    if is_buy and args.sl >= args.entry:
        print(f"ERROR: long SL ({args.sl}) harus < entry ({args.entry})", file=sys.stderr)
        sys.exit(2)
    if not is_buy and args.sl <= args.entry:
        print(f"ERROR: short SL ({args.sl}) harus > entry ({args.entry})", file=sys.stderr)
        sys.exit(2)

    # SL distance sanity (per STRATEGI-15M.md: max 1.5%)
    sl_pct = abs(args.entry - args.sl) / args.entry * 100
    if sl_pct > 1.5:
        print(f"ERROR: SL distance {sl_pct:.2f}% > 1.5% — terlalu lebar (be wide ≠ careless)",
              file=sys.stderr)
        sys.exit(2)

    main_order = {
        "coin": args.coin,
        "is_buy": is_buy,
        "sz": args.qty,
        "limit_px": args.entry,
        "order_type": {"limit": {"tif": "Gtc"}},
        "reduce_only": False,
    }
    sl_order = {
        "coin": args.coin,
        "is_buy": not is_buy,
        "sz": args.qty,
        "limit_px": args.sl,
        "order_type": {"trigger": {"triggerPx": args.sl, "isMarket": True, "tpsl": "sl"}},
        "reduce_only": True,
    }
    tp_order = {
        "coin": args.coin,
        "is_buy": not is_buy,
        "sz": args.qty,
        "limit_px": args.tp1,
        "order_type": {"trigger": {"triggerPx": args.tp1, "isMarket": False, "tpsl": "tp"}},
        "reduce_only": True,
    }

    print(f"=== HL PLACE ORDER {'(DRY-RUN — tidak dikirim)' if DRY_RUN else '(REAL)'} ===")
    print(f"Main entry: {json.dumps(main_order)}")
    print(f"SL trigger: {json.dumps(sl_order)}")
    print(f"TP trigger: {json.dumps(tp_order)}")
    print(f"\nSL distance: {sl_pct:.3f}%")

    if DRY_RUN:
        print(f"\n→ DRY_RUN aktif (HL_DRY_RUN={os.getenv('HL_DRY_RUN','1')}).")
        print(f"→ Untuk real: HL_DRY_RUN=0 ... --confirm")
        return

    if not args.confirm:
        print(f"\n→ ERROR: real order butuh --confirm flag.", file=sys.stderr)
        sys.exit(2)

    info, exchange, main_addr, _ = get_clients()

    print(f"\n→ Placing main limit order...")
    res1 = exchange.order(
        args.coin, is_buy, args.qty, args.entry,
        {"limit": {"tif": "Gtc"}}, reduce_only=False,
    )
    print(f"  result: {json.dumps(res1)}")
    if res1.get("status") != "ok":
        print("✗ Main order failed, skipping SL/TP")
        sys.exit(1)

    print(f"\n→ Placing SL trigger (market)...")
    res2 = exchange.order(
        args.coin, not is_buy, args.qty, args.sl,
        {"trigger": {"triggerPx": args.sl, "isMarket": True, "tpsl": "sl"}},
        reduce_only=True,
    )
    print(f"  result: {json.dumps(res2)}")

    print(f"\n→ Placing TP1 trigger (limit)...")
    res3 = exchange.order(
        args.coin, not is_buy, args.qty, args.tp1,
        {"trigger": {"triggerPx": args.tp1, "isMarket": False, "tpsl": "tp"}},
        reduce_only=True,
    )
    print(f"  result: {json.dumps(res3)}")

    if args.tp2:
        print(f"\nNote: TP2 ({args.tp2}) NOT placed automatically.")
        print(f"      Place setelah TP1 hit + posisi tinggal sisa.")


def cmd_position(args):
    info, _, main_addr, _ = get_clients()
    state = info.user_state(main_addr)
    positions = state.get("assetPositions", [])
    target = [
        p for p in positions
        if (args.coin is None or p["position"]["coin"] == args.coin)
        and float(p["position"]["szi"]) != 0
    ]
    if not target:
        print(f"No active position{'.' if not args.coin else f' for {args.coin}.'}")
        return
    for p in target:
        pos = p["position"]
        side = "LONG" if float(pos["szi"]) > 0 else "SHORT"
        print(f"=== {pos['coin']} {side} ===")
        print(f"  Size       : {pos['szi']}")
        print(f"  Entry px   : {pos['entryPx']}")
        print(f"  Mark px    : {pos.get('markPx', 'n/a')}")
        print(f"  Unrealized : {pos.get('unrealizedPnl', 'n/a')}")
        print(f"  Liq price  : {pos.get('liquidationPx', 'n/a')}")
        print(f"  Margin     : {pos.get('marginUsed', 'n/a')}")


def cmd_cancel_all(args):
    info, exchange, main_addr, _ = get_clients()
    orders = info.open_orders(main_addr)
    if args.coin:
        orders = [o for o in orders if o["coin"] == args.coin]

    print(f"=== HL CANCEL {len(orders)} ORDERS "
          f"({args.coin or 'ALL'}) {'(DRY-RUN)' if DRY_RUN else '(REAL)'} ===")
    for o in orders[:5]:
        print(f"  {o['coin']} {o['side']} sz={o['sz']} px={o['limitPx']} oid={o['oid']}")
    if len(orders) > 5:
        print(f"  ... + {len(orders) - 5} more")

    if not orders:
        print("No orders to cancel.")
        return

    if DRY_RUN:
        print("\nDRY_RUN aktif — no orders cancelled.")
        return
    if not args.confirm:
        print("\nERROR: butuh --confirm", file=sys.stderr); sys.exit(2)

    cancels = [{"coin": o["coin"], "oid": o["oid"]} for o in orders]
    result = exchange.bulk_cancel(cancels)
    print(f"\nResult: {json.dumps(result, indent=2)}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("preflight")

    p_place = sub.add_parser("place")
    p_place.add_argument("--coin", required=True, help="BTC, ETH, SOL, HYPE (no /USDC)")
    p_place.add_argument("--side", choices=["long", "short"], required=True)
    p_place.add_argument("--qty", type=float, required=True)
    p_place.add_argument("--entry", type=float, required=True)
    p_place.add_argument("--sl", type=float, required=True)
    p_place.add_argument("--tp1", type=float, required=True)
    p_place.add_argument("--tp2", type=float, default=None)
    p_place.add_argument("--confirm", action="store_true")

    p_pos = sub.add_parser("position")
    p_pos.add_argument("--coin", default=None)

    p_cancel = sub.add_parser("cancel-all")
    p_cancel.add_argument("--coin", default=None)
    p_cancel.add_argument("--confirm", action="store_true")

    args = ap.parse_args()
    {"preflight": cmd_preflight, "place": cmd_place,
     "position": cmd_position, "cancel-all": cmd_cancel_all}[args.cmd](args)


if __name__ == "__main__":
    main()
