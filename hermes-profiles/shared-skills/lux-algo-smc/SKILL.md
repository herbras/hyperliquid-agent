---
name: lux-algo-smc
description: Playbook scalping Lux Algo SMC (BOS, CHoCH, OB, FVG, Premium/Discount). 4-langkah workflow + 3 setup high win-rate + skip rules.
version: 1.0.0
metadata:
  hermes:
    tags: [trading, scalping, smc, lux-algo, crypto]
    category: trading
    config:
      - key: lux-algo-smc.playbook_path
        description: "Absolute path ke lux-algo-guide-verified-v2.md"
        default: "~/Documents/panduan-openclaw/hyperliquid/lux-algo-guide-verified-v2.md"
        prompt: "Path ke playbook file"
---

# Lux Algo SMC — Scalping Playbook

Skill ini me-load playbook scalping berbasis Smart Money Concepts (Lux Algo).
Konten lengkap ada di `references/lux-algo-guide.md` — copy dari
`hyperliquid/lux-algo-guide-verified-v2.md`.

## When to Use

Trigger skill ini kalau user:
- Tanya "setup A/B/C di pair X"
- Minta "hitung entry/SL/TP per playbook"
- Tanya istilah SMC: BOS, CHoCH, OB, FVG, EQH/EQL, Premium/Discount

## Procedure

1. **Tentukan langkah workflow** yang user tuju (1-4):
   - Step 1: 15m bias → cek Swing BOS, Discount Zone, Fresh OB
   - Step 2: 5m setup → CHoCH/BOS + OB/FVG dalam Discount + volume
   - Step 3: konfirmasi entry → wait candle close, candle ke-3 entry
   - Step 4: risk → SL 0.2% di bawah OB low, TP1 swing high, RR ≥1:2

2. **Validasi confluence** — minimum 3 dari 4 ini harus align:
   - Macro bias 15m searah trade
   - OB fresh (belum disentuh) atau FVG fresh
   - Harga di Discount/Premium yang tepat
   - Volume rejection > volume entry-ke-OB

3. **Hitung level** sesuai aturan Setup A/B/C di playbook.

4. **Cek SKIP conditions** dulu sebelum confirm entry. Lihat section
   "Kondisi SKIP — Wajib Diabaikan" di playbook. 7 trigger SKIP:
   choppy, no fresh OB, equilibrium zone, EQH di atas TP, event window,
   weekend gap, 2-SL hari ini.

## Pitfalls

- Intracandle entry — paling umum, paling fatal. Wait candle CLOSE.
- SL terlalu dekat → kena noise → loss. 0.2% buffer wajib.
- Skip TP1 karena greedy — TP1 50% posisi adalah sacred.
- Trade saat ranging — choppy market = setup A/B/C semua gagal.

## Verification

Sebelum confirm setup ke user:
1. Sebut nama setup (A / B / C) eksplisit
2. List confluence yang align (minimum 3)
3. List confluence yang tidak align (kalau ada — pertimbangkan SKIP)
4. SL distance dalam % (harus < 1%)
5. RR minimum 1:1.5, target 1:2

Kalau ada satu syarat tidak terpenuhi → SKIP setup, jangan dipaksa.

## References

- `references/lux-algo-guide.md` — playbook lengkap (verbatim dari panduan-openclaw)
