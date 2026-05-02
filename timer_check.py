#!/usr/bin/env python3
"""
timer_check.py — baca open-positions.json, output reminder kalau posisi
sudah lewat checkpoint 5/20/40/60 menit dari open time.

Format open-positions.json:
[
  {
    "id": "btc-2025-04-30-1423",
    "pair": "BTC",
    "side": "long",
    "entry": 67380,
    "sl": 67250,
    "tp1": 67700,
    "tp2": 67950,
    "opened_at": "2025-04-30T14:23:00Z",
    "tp1_hit": false,
    "be_moved": false,
    "checkpoints_seen": []   <- tracking biar reminder ga double-fire
  }
]

Stdout cuma populated kalau ada checkpoint baru. Jika silent → cron exit clean.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# Checkpoints disesuaikan ke STRATEGI-15M.md (timer 180 menit / 3 jam).
# 12 candle 15m = 3 jam. Be wide, kasih posisi ruang gerak.
CHECKPOINTS = [
    (15,  "Posisi 15 menit (1 candle 15m close). Jangan sentuh, biarkan setup berkembang. Be patient."),
    (60,  "1 jam elapsed (4 candle 15m). Cek: bias 1h masih align? OB intact? Kalau kembali ke tengah OB tanpa rejection candle, pertimbangkan exit."),
    (120, "2 jam elapsed (8 candle 15m). Cek Internal CHoCH/BOS counter-trend di 15m. Kalau ada, atau harga close di luar OB, EXIT sekarang."),
    (180, "3 JAM HABIS. EXIT MANUAL SEKARANG. Tidak ada diskusi. Setup gagal develop dalam timer."),
]


def main():
    pf = os.path.expanduser(os.environ.get(
        "POSITIONS_FILE",
        "~/.hermes/profiles/scalper-journal/state/open-positions.json",
    ))
    p = Path(pf)
    if not p.exists():
        return  # silent: no positions

    with p.open() as f:
        positions = json.load(f)

    if not isinstance(positions, list) or not positions:
        return

    now = datetime.now(timezone.utc)
    output_lines = []
    dirty = False

    for pos in positions:
        try:
            opened = datetime.fromisoformat(pos["opened_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        elapsed_min = int((now - opened).total_seconds() // 60)
        seen = set(pos.get("checkpoints_seen", []))

        # TP1 hit + BE belum di-move = reminder khusus
        if pos.get("tp1_hit") and not pos.get("be_moved") and "be_reminder" not in seen:
            output_lines.append(
                f"⚠ {pos['pair']} {pos['side'].upper()}: TP1 hit. "
                f"PINDAHKAN SL KE BREAKEVEN ({pos['entry']}) SEKARANG. Wajib."
            )
            seen.add("be_reminder")
            dirty = True

        for minutes, msg in CHECKPOINTS:
            if elapsed_min >= minutes and f"t{minutes}" not in seen:
                output_lines.append(
                    f"[{pos['pair']} {pos['side'].upper()} @ {pos['entry']}] "
                    f"+{minutes}m — {msg}"
                )
                seen.add(f"t{minutes}")
                dirty = True

        pos["checkpoints_seen"] = sorted(seen)

    if dirty:
        with p.open("w") as f:
            json.dump(positions, f, indent=2)

    if output_lines:
        print("\n\n".join(output_lines))


if __name__ == "__main__":
    main()
