# Catatan: Apa yang Sedang Kita Bangun

> Doc santai. Untuk re-orient kalau lupa atau buat orang baru yang mau ngerti
> sistem ini.

## Goal besar

Sistem scalping crypto yang **bisa dipercayakan ke agent**, bukan jadi tempat
panik tiap jam. Filosofinya:

> **Be good, be wide.**
>
> Patient di entry. Lebar di stop. Selective di setup. Pasrahin ke cron, jangan
> ngehek chart tiap menit.

Ini lawan dari "scalping 1m + 50 trade per hari" yang biasanya bikin trader
burnt-out dan akun habis.

## Kenapa pakai Hermes Agent

Hermes punya **profile system** — tiap profile = satu agent dengan SOUL,
config, dan cron sendiri. Jadi kita bisa pisahin peran:

| Profile | Peran | Kapan jalan |
|---|---|---|
| `scalper-scout` | Scanner: cek bias 15m, filter pair, kasih shortlist | Cron auto, cuma di Asia + US window |
| `scalper-sniper` | Setup hunter: hitung entry/SL/TP per playbook, enforce SKIP rules | Manual, saat scout fire alert |
| `scalper-journal` | Trade manager: timer reminder, BE rule, 2-SL stop, daily review | Cron tiap 5 menit kalau ada open posisi |

Pisahin 3 agent = tiap agent context-nya kecil dan spesifik. Bukan satu
agent serbabisa yang akhirnya generic.

## Keputusan kunci yang sudah dibuat

### 1. Timeframe execution: 15m (bukan 5m)

Playbook awal `lux-algo-guide-verified-v2.md` pakai 5m execution dengan 15m
bias. Setelah review, kita pindah ke **15m execution** karena:

- 5m noise tinggi → SL kena fakeout terlalu sering
- 5m butuh fokus tinggi → ga sustainable harian
- 15m setup A reliability lebih tinggi (less false BOS/CHoCH)
- 15m bias context-nya jadi 1h (bukan 15m)

Yang berubah:
- Bias: dari 15m → **1h** (lihat ema21 dan swing structure di 1h)
- Execution: dari 5m → **15m**
- Stop loss buffer: 0.2% → **0.3-0.4%** (15m noise lebih lebar = "be wide")
- Risk per trade: tetap 0.5-1% (jangan naik proporsional, RR jadi 1:2-1:3)
- Timer: 60 menit → **180 menit / 3 jam** (12 candle 15m)

Detail lengkap: `STRATEGI-15M.md`.

### 2. Window aktif: Asia + US, bukan 24/7

Cron scout cuma fire di window dengan volume + volatility tinggi. Sisanya
silent — tidak ada alert, tidak ada noise.

| Window UTC | Lokal Jakarta (WIB +7) | Catatan |
|---|---|---|
| 00:00–04:00 | 07:00–11:00 | Tokyo open + Asia core. Pair Asia (BNB, XRP, TON, HYPE) bagus di sini. |
| 13:00–17:00 | 20:00–00:00 | NY pre-market + core NY. BTC/ETH/SOL volume tertinggi. |

Total: **8 jam aktif / 24 jam = 33%**. Cron expression: `*/15 0-3,13-16 * * 1-5`.

Yang **TIDAK** kita pantau:
- 04:00–13:00 UTC (London early — overlap dengan Asia close, biasanya ranging)
- 17:00–00:00 UTC (NY close → Asia pre-open dead zone)
- Sabtu-Minggu (kecuali Sun 23:00 UTC sebagai opsional Asia open)

Catatan: playbook awal bilang "Skip Asia session" — itu untuk BTC/ETH di
era 2020-2022. Sekarang Asia volatil banget, terutama untuk pair yang trade
di Hyperliquid (banyak retail Asia).

### 3. Filosofi "be good, be wide" — implementasi konkret

**Be good:**
- Sniper default ke Setup A (continuation, paling reliable). Setup B/C cuma
  kalau A tidak ada DAN confluence ≥ 4 faktor align.
- Target 1-2 trade per session, bukan 5+.
- Kalau 1 SL di session pertama → stop, lanjut session berikutnya. Bukan
  "revenge trade".

**Be wide:**
- SL buffer naik dari 0.2% → 0.3-0.4% (15m noise lebih besar).
- TP1 lebih jauh (next swing high di 15m, bukan 5m).
- Timer 3 jam, bukan 60 menit. Kasih posisi ruang gerak.
- RR target 1:2 minimum, push ke 1:3 kalau confluence kuat.

**Bukan ngepet:**
- Cron yang nyari sinyal, bukan kita.
- Telegram alert cuma fire kalau ada GO-LONG/GO-SHORT di scout, atau
  reminder di journal. Skip-only scan = silent.
- User cek HP cuma saat ding. Kalau ga ding 4 jam, artinya ga ada apa-apa.
  Itu bagus — bukan kerugian.

## Arsitektur file

```
hyperliquid/
├── lux-algo-guide-verified-v2.md      # playbook original (5m, dijadikan referensi)
├── STRATEGI-15M.md                    # playbook 15m + session windows (BARU)
├── CATATAN.md                         # dokumen ini
├── fetch_market_data.py               # ccxt generic (Binance dst)
├── fetch_hyperliquid.py               # Hyperliquid native
├── notify_telegram.py                 # helper push ke Telegram
├── timer_check.py                     # baca posisi + reminder timer
├── crypto-trader-signals-v4.skill     # binary skill bundled
└── hermes-profiles/
    ├── README.md                      # cara install
    ├── CATATAN.md                     # → ini juga ada di sini (canonical di parent)
    ├── scalper-scout/                 # 1h bias + 15m FVG scanner
    │   ├── config.yaml
    │   ├── SOUL.md
    │   ├── .env.example
    │   └── cron/
    │       ├── market-scan.yaml                # ccxt mode
    │       └── market-scan-hyperliquid.yaml    # HL native mode
    ├── scalper-sniper/                # 15m setup hunter (Setup A/B/C)
    │   ├── config.yaml
    │   ├── SOUL.md
    │   └── .env.example
    ├── scalper-journal/               # trade manager + post-mortem
    │   ├── config.yaml
    │   ├── SOUL.md
    │   ├── .env.example
    │   └── cron/
    │       └── timer-check.yaml
    └── shared-skills/
        ├── lux-algo-smc/SKILL.md
        └── market-data-cron/SKILL.md
```

## Flow harian (contoh hari ideal)

```
07:00 WIB (00:00 UTC) — Asia window mulai
  Cron scout fire `/scan`. Output: BTC GO-LONG, fresh bull FVG.
  → Telegram ding: "🎯 SCOUT 15m: BTC GO-LONG ..."

07:15 WIB — Saya buka HP, lihat alert.
  Buka chat scalper-sniper di Hermes.
  "BTC bias bullish, FVG 67310-67370, fresh. Cari setup A di 15m."
  Sniper reply: "Setup A valid. Entry 67380 limit, SL 67220, TP1 67780,
  TP2 68150. RR 1:2.5."

07:18 WIB — Pasang limit order di exchange.
  Lapor ke journal:
  "OPEN: BTC long 67380, SL 67220, TP1 67780, TP2 68150, time=2025-04-30 00:18 UTC"
  Journal log ke open-positions.json.

07:33 WIB (00:33 UTC, +15 min) — Cron timer-check fire.
  Telegram: "⏱ JOURNAL: [BTC LONG @67380] +15m. Jangan sentuh, biarkan
  setup berkembang."

08:18 WIB (01:18 UTC, +60 min) — TP1 hit di 67780.
  Saya lapor: "TP1 hit 01:18"
  Journal reply: "MOVE SL TO BREAKEVEN (67380). Sekarang. Wajib."
  Saya pindah SL.

09:30 WIB (02:30 UTC, +132 min) — TP2 hit di 68150.
  Lapor: "TP2 hit, closed full"
  Journal log final, +1.6R.

11:00 WIB (04:00 UTC) — Asia window selesai, cron tidak fire lagi.
  Saya tinggal HP, lanjut kerjaan lain. Tidak ada chart watching.

20:00 WIB (13:00 UTC) — US window mulai, cron fire lagi.
  Hari ini sudah 1 win, mau target 1 trade lagi atau cukup? Pilihan.
  Kalau cukup: jangan trade, biarpun ada signal. Disiplin.

24:00 WIB (17:00 UTC) — US window selesai.
  Buka journal: `/daily`
  Output summary 1-2 trade, win-rate, lessons. Tidur.
```

Total screen time scalping hari ini: **~30 menit total**, bukan 8 jam.

## Yang BELUM dibangun (TODO list)

- [ ] Auto-write `open-positions.json` dari pesan natural-language journal.
      Saat ini user harus manual format ulang. Bisa pakai tool `position-write`
      di journal yang extract pair/entry/SL/TP dari kalimat.
- [ ] Hyperliquid trade execution via SDK (sub-account dengan agent wallet).
      Saat ini sniper cuma kasih level, user manual order.
- [ ] Backtest harness — replay candle history vs SOUL rules untuk validate
      bahwa "be wide" 15m benar-benar lebih profitable di kondisi recent.
- [ ] Auto-detect 2-SL → otomatis touch HALT.flag, bukan manual `/halt`.
- [ ] News/event calendar integration — auto-PAUSE 30 menit sebelum CPI/FOMC.

## Catatan filosofis

Sistem ini **BUKAN** auto-trader. Sistem ini adalah:
1. **Scanner** — biar mata kita ga capek nyari setup
2. **Calculator** — biar emosi ga campur tangan di entry/SL/TP
3. **Accountability** — biar disiplin di BE, timer, 2-SL stop

Decision tetap di tangan kita. Eksekusi tetap manual (saat ini). Itu bagus —
agent error tidak langsung kosongin akun.

> **Aturan emas:** kalau alert fire dan kita ga punya headspace untuk eksekusi
> dengan tenang, **skip**. Setup A berikutnya akan datang. Selalu ada.
