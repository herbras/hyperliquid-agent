#!/usr/bin/env python3
"""
position_write.py — parse pesan natural-language dan tulis ke open-positions.json.

Pakai:
  python3 position_write.py open "OPEN: BTC long 67380, SL 67110, TP1 67980, TP2 68450"
  python3 position_write.py close BTC tp1
  python3 position_write.py close BTC sl
  python3 position_write.py move-be BTC
  python3 position_write.py list

Format JSON:
[
  {
    "id": "btc-1714478580",
    "pair": "BTC",
    "side": "long",
    "entry": 67380, "sl": 67110, "tp1": 67980, "tp2": 68450,
    "opened_at": "2025-04-30T14:23:00Z",
    "tp1_hit": false, "be_moved": false, "checkpoints_seen": [],
    "off_window": false
  }
]
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


POS_FILE = Path(os.path.expanduser(
    os.environ.get("POSITIONS_FILE",
                   "~/.hermes/profiles/scalper-journal/state/open-positions.json")
))
HISTORY_FILE = POS_FILE.parent / "trade-history.jsonl"
LESSONS_FILE = POS_FILE.parent / "LESSONS.md"


def load() -> list:
    if not POS_FILE.exists():
        return []
    with POS_FILE.open() as f:
        return json.load(f)


def save(positions: list):
    POS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with POS_FILE.open("w") as f:
        json.dump(positions, f, indent=2)


def append_history(entry: dict):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def is_off_window() -> bool:
    """True kalau jam UTC sekarang di luar 00-04 atau 13-17."""
    h = datetime.now(timezone.utc).hour
    return not (0 <= h < 4 or 13 <= h < 17)


def parse_open(text: str) -> dict:
    """
    Parse: "OPEN: BTC long 67380, SL 67110, TP1 67980, TP2 68450"
    Toleran terhadap variasi spacing, urutan, case.
    """
    t = text.strip()
    # pair + side
    m = re.search(r"\b([A-Z]{2,8})\s+(long|short|buy|sell)\b", t, re.IGNORECASE)
    if not m:
        raise ValueError(f"Tidak ketemu pair+side. Format: '<PAIR> long/short ...'")
    pair = m.group(1).upper()
    side = m.group(2).lower()
    if side in ("buy",): side = "long"
    if side in ("sell",): side = "short"

    # entry — angka pertama setelah side
    entry_match = re.search(rf"\b{re.escape(side)}\b[^\d]*([\d.]+)", t, re.IGNORECASE)
    if not entry_match:
        raise ValueError("Entry price tidak ditemukan")
    entry = float(entry_match.group(1))

    # SL, TP1, TP2, TP3
    levels = {}
    for key in ["SL", "TP1", "TP2", "TP3"]:
        m = re.search(rf"\b{key}\b[^\d-]*([\d.]+)", t, re.IGNORECASE)
        if m:
            levels[key.lower()] = float(m.group(1))

    if "sl" not in levels:
        raise ValueError("SL wajib")
    if "tp1" not in levels:
        raise ValueError("TP1 wajib")

    now = datetime.now(timezone.utc)
    pos = {
        "id": f"{pair.lower()}-{int(now.timestamp())}",
        "pair": pair,
        "side": side,
        "entry": entry,
        "sl": levels["sl"],
        "tp1": levels["tp1"],
        "tp2": levels.get("tp2"),
        "tp3": levels.get("tp3"),
        "opened_at": now.isoformat().replace("+00:00", "Z"),
        "tp1_hit": False,
        "be_moved": False,
        "checkpoints_seen": [],
        "off_window": is_off_window(),
    }
    return pos


def cmd_open(args):
    text = " ".join(args)
    pos = parse_open(text)
    positions = load()
    if any(p["pair"] == pos["pair"] for p in positions):
        print(f"WARNING: posisi {pos['pair']} sudah ada. Append anyway? "
              "Hapus dulu dengan `close` kalau salah.")
    positions.append(pos)
    save(positions)
    flag = " [OFF-WINDOW]" if pos["off_window"] else ""
    print(f"OK opened {pos['pair']} {pos['side']} @ {pos['entry']} "
          f"SL={pos['sl']} TP1={pos['tp1']}{flag}")
    print(f"Timer: 180 menit (3 jam). Reminder via cron timer-check.")
    if pos["off_window"]:
        print("⚠ Likuidity rendah di luar window aktif. Watch slippage.")


def cmd_close(args):
    if len(args) < 2:
        print("Usage: close <PAIR> <reason: tp1|tp2|tp3|sl|be|manual>")
        sys.exit(2)
    pair = args[0].upper()
    reason = args[1].lower()
    positions = load()
    found = None
    remaining = []
    for p in positions:
        if p["pair"] == pair and not found:
            found = p
        else:
            remaining.append(p)
    if not found:
        print(f"ERROR: posisi {pair} tidak ditemukan")
        sys.exit(1)

    # Hitung R-multiple — pakai original_sl (sebelum move-be) sebagai basis risk
    risk_basis = found.get("original_sl", found["sl"])
    risk = abs(found["entry"] - risk_basis)
    if reason == "sl":
        r_mult = -1.0
    elif reason in ("tp1", "tp2", "tp3"):
        target = found.get(reason)
        if target is None:
            print(f"ERROR: {reason} tidak ada di posisi")
            sys.exit(1)
        diff = target - found["entry"] if found["side"] == "long" else found["entry"] - target
        r_mult = round(diff / risk, 2) if risk else 0
    elif reason == "be":
        r_mult = 0.0
    else:  # manual
        r_mult = None  # user input later

    save(remaining)
    history = {
        "id": found["id"],
        "pair": found["pair"],
        "side": found["side"],
        "entry": found["entry"],
        "sl": found["sl"],
        "tp1": found["tp1"],
        "tp2": found.get("tp2"),
        "opened_at": found["opened_at"],
        "closed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "exit_reason": reason,
        "r_multiple": r_mult,
        "off_window": found.get("off_window", False),
        "tp1_hit_during": found.get("tp1_hit", False),
    }
    append_history(history)
    print(f"OK closed {pair} via {reason}, R={r_mult}")


def cmd_move_be(args):
    if not args:
        print("Usage: move-be <PAIR>")
        sys.exit(2)
    pair = args[0].upper()
    positions = load()
    found = False
    for p in positions:
        if p["pair"] == pair:
            # Preserve original_sl agar R-multiple tetap akurat saat close
            if "original_sl" not in p:
                p["original_sl"] = p["sl"]
            p["sl"] = p["entry"]
            p["be_moved"] = True
            p["tp1_hit"] = True
            found = True
    if not found:
        print(f"ERROR: posisi {pair} tidak ditemukan")
        sys.exit(1)
    save(positions)
    print(f"OK SL {pair} dipindah ke breakeven.")


def cmd_list(args):
    positions = load()
    if not positions:
        print("[]")
        return
    print(json.dumps(positions, indent=2))


def cmd_stats(args):
    """Hitung stats dari trade-history.jsonl untuk hari ini / minggu ini."""
    if not HISTORY_FILE.exists():
        print("No trade history yet.")
        return
    scope = args[0] if args else "today"  # today|week|all
    now = datetime.now(timezone.utc)
    cutoff = None
    if scope == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif scope == "week":
        from datetime import timedelta
        cutoff = now - timedelta(days=7)

    trades = []
    with HISTORY_FILE.open() as f:
        for line in f:
            t = json.loads(line)
            if cutoff:
                ct = datetime.fromisoformat(t["closed_at"].replace("Z", "+00:00"))
                if ct < cutoff:
                    continue
            trades.append(t)

    if not trades:
        print(f"No trades in scope={scope}")
        return

    wins = [t for t in trades if (t.get("r_multiple") or 0) > 0]
    losses = [t for t in trades if (t.get("r_multiple") or 0) < 0]
    total_r = sum(t.get("r_multiple") or 0 for t in trades)
    wr = round(len(wins) / len(trades) * 100, 1) if trades else 0
    avg_r = round(total_r / len(trades), 2) if trades else 0

    print(f"=== Stats ({scope}, n={len(trades)}) ===")
    print(f"Win rate : {wr}%  ({len(wins)}W / {len(losses)}L)")
    print(f"Total R  : {total_r:+.2f}")
    print(f"Avg R    : {avg_r:+.2f}")
    sl_count = sum(1 for t in trades if t["exit_reason"] == "sl")
    print(f"SL hit   : {sl_count}")
    if sl_count >= 2 and scope == "today":
        print("⚠ 2-SL daily limit. HALT recommended.")


COMMANDS = {
    "open": cmd_open,
    "close": cmd_close,
    "move-be": cmd_move_be,
    "list": cmd_list,
    "stats": cmd_stats,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
