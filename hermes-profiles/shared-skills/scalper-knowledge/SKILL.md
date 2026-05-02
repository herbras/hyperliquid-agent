---
name: scalper-knowledge
description: Knowledge base agregat untuk scalping 15m — playbook, decision log, lessons learned, trade history. Sumber tunggal of truth untuk coach & sniper guidance.
version: 1.0.0
metadata:
  hermes:
    tags: [trading, scalping, knowledge, playbook]
    category: trading
    config:
      - key: scalper-knowledge.strategi_path
        description: "Path ke STRATEGI-15M.md"
        default: "~/Documents/panduan-openclaw/hyperliquid/STRATEGI-15M.md"
      - key: scalper-knowledge.catatan_path
        description: "Path ke CATATAN.md"
        default: "~/Documents/panduan-openclaw/hyperliquid/hermes-profiles/CATATAN.md"
      - key: scalper-knowledge.playbook_5m_path
        description: "Path ke playbook original 5m (referensi)"
        default: "~/Documents/panduan-openclaw/hyperliquid/lux-algo-guide-verified-v2.md"
      - key: scalper-knowledge.lessons_path
        description: "Path ke LESSONS.md (dynamic, di-update coach)"
        default: "~/.hermes/profiles/scalper-journal/state/LESSONS.md"
      - key: scalper-knowledge.history_path
        description: "Path ke trade-history.jsonl"
        default: "~/.hermes/profiles/scalper-journal/state/trade-history.jsonl"
---

# Scalper Knowledge Base

Skill ini bukan procedural — ini **referensi**. Agent yang load skill ini
dapat akses ke 5 sumber pengetahuan:

## Hierarki sumber (dari yang paling otoritatif)

1. **`LESSONS.md`** — paling otoritatif. Rules dari trading nyata yang
   override atau melengkapi playbook static. Coach update via debrief/weekly.
2. **`STRATEGI-15M.md`** — playbook utama saat ini (15m + Asia/US window
   + be wide).
3. **`CATATAN.md`** — decision log + filosofi. Konteks "kenapa" dari
   keputusan yang dibuat.
4. **`trade-history.jsonl`** — data hard. Empirical evidence dari trade
   yang sudah closed.
5. **`lux-algo-guide-verified-v2.md`** — playbook original 5m. Referensi
   background untuk konsep SMC (BOS, CHoCH, OB, FVG, EQH/EQL).

## Aturan akses

Saat agent jawab pertanyaan / kasih guidance:

1. **Check LESSONS.md dulu.** Kalau ada rule yang relevan dari pengalaman
   nyata, itu menang dari playbook static.
2. **Lalu STRATEGI-15M.md.** Playbook current.
3. **Cite source explicitly.** Setiap claim harus bisa di-trace:
   `Per STRATEGI-15M.md section "X": ...`
4. **Kalau conflict** antara LESSONS dan STRATEGI:
   - LESSONS lebih recent dan berbasis evidence → menang
   - Kecuali kalau LESSONS entry sangat lama (>3 bulan) atau sample size
     terlalu kecil (n<5), pakai STRATEGI sebagai default
5. **Tidak halusinasi.** Kalau pertanyaan tidak ada di KB, bilang "tidak
   ada di KB, bisa kamu klarifikasi atau tambahkan ke LESSONS.md?"

## Reference layout

```
references/
├── STRATEGI-15M.md              # static, jarang berubah
├── CATATAN.md                   # static, jarang berubah
└── lux-algo-guide.md            # static, referensi background
```

Path dynamic (di luar references/) yang harus dibaca runtime:
- `~/.hermes/profiles/scalper-journal/state/LESSONS.md`
- `~/.hermes/profiles/scalper-journal/state/trade-history.jsonl`
- `~/.hermes/profiles/scalper-journal/state/open-positions.json`

## Common queries (template jawaban)

### "Setup A definisi-nya apa?"
→ Cite STRATEGI-15M.md section "3 Setup di 15m → Setup A".

### "Kapan harus skip Setup B?"
→ Cite STRATEGI-15M.md "Setup B" + check LESSONS.md "Rules from experience".

### "Aku rugi Setup C terus, gimana?"
→ Aggregate trade-history.jsonl filter Setup C, kasih win-rate,
recommend skip kalau WR < 40%.

### "Window aktif sekarang?"
→ Kasih waktu UTC sekarang vs window 00-04 atau 13-17. Kalau di luar,
jelaskan kenapa skip per filosofi "be wide".
