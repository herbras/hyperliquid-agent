# Strategi Scalping 15m — "Be Good, Be Wide"

Addendum dari `lux-algo-guide-verified-v2.md` (yang aslinya 5m execution).
Dokumen ini override beberapa parameter karena kita pindah ke **15m
execution** + **session windows** + **patient discipline**.

---

## TL;DR perbedaan dari playbook 5m

| Parameter | Playbook 5m (lama) | Strategi 15m (baru) |
|---|---|---|
| Bias timeframe | 15m | **1h** |
| Execution timeframe | 5m | **15m** |
| SL buffer | 0.2% | **0.3-0.4%** |
| Timer max | 60 menit | **180 menit (3 jam)** |
| Target trade/sesi | 2-4 setup | **1-2 setup** |
| Win rate target | 48-62% | **55-65%** (selective lebih tinggi) |
| Session aktif | London + NY (07-17 UTC) | **Asia + US (00-04 + 13-17 UTC)** |
| Frequency check | Tiap 5 menit | **Tiap 15 menit, hanya di window** |

---

## Filosofi "Be Good, Be Wide"

### Be Good — quality over quantity

> Lebih baik 1 trade Setup A dengan win rate 70% daripada 5 trade Setup B/C
> dengan win rate 50%.

- **Default ke Setup A.** Continuation (OB retest setelah Swing BOS) adalah
  setup paling reliable. Setup B (CHoCH reversal) dan C (sweep) cuma diambil
  kalau Setup A tidak ada DAN confluence ≥4 faktor align.
- **Skip aggressively.** 7 kondisi SKIP di playbook tetap berlaku. Tambah:
  jika dalam window aktif tidak ada Setup A muncul, **biarkan saja**. Bukan
  setiap window harus ada trade.
- **Tidak ada revenge trade.** Kalau 1 SL di Asia window, US window boleh
  trade lagi tapi cuma Setup A dengan ≥4 confluence. Kalau 2 SL = HALT.

### Be Wide — kasih ruang gerak

> 15m candle range ~3x 5m candle range. SL yang ngepet di 15m = SL kena noise.

- **SL buffer 0.3-0.4%**, bukan 0.2%. 15m wick lebih dalam.
- **Timer 3 jam**, bukan 60 menit. 15m setup butuh 12 candle untuk develop.
- **TP1 di next swing high 15m** (lebih jauh dari swing high 5m). RR target
  1:2 minimum, target ideal 1:3.
- **Posisi sizing tetap 0.5-1% risk per trade** — jangan naikin proporsional
  dengan SL distance. Yang naik adalah RR (kalau SL lebih lebar tapi TP juga
  lebih jauh, RR sama atau lebih bagus).

### Bukan Ngepet — let cron do the watching

> Pantau chart 8 jam = burnt out. Pantau alert 30 menit = sustainable.

- **Cron scan tiap 15 menit** di window aktif. Sync dengan candle close 15m.
- **Telegram alert filter ketat:** scan kosong (semua SKIP) = silent.
  Hanya GO-LONG / GO-SHORT yang fire.
- **Journal timer push reminder otomatis.** Tidak perlu set timer manual.
- **Aturan personal:** kalau lagi tidak fokus / lagi meeting / lagi capek,
  **abaikan alert**. Setup A berikutnya akan datang.

---

## Window aktif (UTC)

```
┌──────────── ASIA WINDOW ────────────┐    ┌──── DEAD ────┐    ┌──── US WINDOW ────┐    ┌──── DEAD ────┐
│  00:00 - 04:00 UTC                  │    │ 04:00-13:00  │    │ 13:00 - 17:00 UTC │    │ 17:00-00:00  │
│  07:00 - 11:00 WIB                  │    │ London early │    │ 20:00 - 00:00 WIB │    │ NY late      │
│                                     │    │ + lunch break│    │                   │    │              │
│  • Tokyo open                       │    │ Skip.        │    │ • NY pre-market   │    │ Skip.        │
│  • JP/KR/SG retail aktif            │    │              │    │ • US data release │    │              │
│  • HYPE, BNB, XRP volatile          │    │              │    │ • CPI/NFP/FOMC    │    │              │
│  • BTC/ETH lumayan kencang          │    │              │    │ • BTC/ETH peak vol│    │              │
└─────────────────────────────────────┘    └──────────────┘    └───────────────────┘    └──────────────┘
```

**Hari aktif:** Senin-Jumat. Sabtu volume rendah, Minggu volume rendah
(kecuali 23:00 UTC Minggu = Asia open Senin, ini **boleh** trade kalau ada
Setup A jelas).

**Cron schedule:** `*/15 0-3,13-16 * * 1-5`
(setiap 15 menit, jam 00-03 dan 13-16 UTC, Senin-Jumat)

---

## Workflow 4 langkah — versi 15m

### Langkah 1: Establish bias di 1h (bukan 15m lagi)

Cek 1h chart:
- Apakah ada **Swing BOS bullish terbaru** di 1h? (solid line besar di Lux Algo)
- Apakah harga di **Discount Zone** 1h?
- Apakah ada **Fresh Swing OB** di 1h dekat harga (< 2% dari current price)?

Kalau semua ya → BULLISH BIAS untuk 15m execution.
Kalau sebaliknya → BEARISH BIAS.
Kalau mix atau choppy → NO BIAS, skip session ini.

**Catatan untuk Asia window:** kadang 1h struktur baru forming (post-NY close).
Cek juga **4h bias** untuk safety net. Kalau 4h dan 1h conflict, pilih 4h.

### Langkah 2: Tunggu setup di 15m

Dengan bullish bias dari 1h, cari di 15m:

1. **Internal CHoCH bullish** atau **Internal BOS bullish setelah pullback**
   (yang kedua lebih aman, prefer ini)
2. Harga di / dekat:
   - **Fresh Internal Bullish OB** (kotak hijau Lux Algo, belum disentuh)
   - **DAN/ATAU Bullish FVG** di bawah harga
   - **DAN harga di Discount Zone** 1h (lihat garis P/D di 1h)
3. **Volume candle** > rata-rata 10 candle terakhir di 15m. Volume yang
   bentuk OB/CHoCH idealnya tinggi.
4. **Confluence minimum 3 dari 4** untuk Setup A. Untuk Setup B/C minimum 4.

### Langkah 3: Konfirmasi entry

JANGAN entry kalau:
- Candle signal belum CLOSE
- Masih dalam OB tapi belum ada rejection candle
- Volume candle masuk OB > volume rejection candle

ENTRY setelah:
1. Candle masuk ke OB → **wait close**
2. Candle berikutnya open dan terlihat bullish (body > wick bawah)
3. Entry di **OPEN candle ke-3** dari saat OB pertama kali tersentuh

Tipe entry:
- **Conservative (preferred):** Limit di 50% zone OB
- **Standard:** Market setelah konfirmasi candle ke-2 (closed bullish)

### Langkah 4: Risk — wide tapi terhitung

**Stop Loss:**
- 0.3-0.4% **di bawah low OB** (buffer untuk noise 15m)
- BUKAN di bawah wick candle signal saja
- Kalau SL > 1.5% dari entry → SKIP, terlalu lebar bahkan untuk 15m

**Take Profit:**
- **TP1 (50% posisi):** swing high 15m terdekat sebelum BOS/CHoCH
- **TP2 (30% posisi):** swing high di 1h, atau OB selanjutnya di 15m
- **TP3 (20% posisi):** trailing 0.5% (lebih lebar dari 5m karena 15m noise)

**RR target:** minimum 1:2, ideal 1:3. Hitung dulu sebelum entry — kalau RR
< 1:2, **skip**.

**Timer (HARD STOP, tidak ada exception):**
- 0–15 menit: jangan sentuh, candle pertama close dulu
- 15–60 menit: cek bias 1h masih align?
- 60–120 menit: cek apakah ada CHoCH/BOS counter-trend di 15m. Kalau ya, exit.
- 120–180 menit: kalau belum hit TP1, **EXIT MANUAL**. Tidak ada diskusi.

**Setelah TP1 hit:**
- **Pindah SL ke breakeven SEKARANG.** Wajib. Tidak negotiable.
- Biarkan TP2 dan TP3 berjalan.

---

## 3 Setup di 15m — adaptasi dari playbook

### Setup A: OB Retest setelah Swing BOS (target utama)

```
Kondisi:
  1h : Swing BOS bullish baru (solid line besar)
  15m: Harga pullback ke zona Swing OB yang terbentuk saat 1h BOS
  15m: OB masih Fresh
  15m: Volume saat masuk OB rendah, volume rejection tinggi
  15m: Harga di Discount Zone 1h

Entry: Limit 50% OB atau market setelah rejection candle close
SL   : 0.4% di bawah low OB
TP1  : Swing high 15m sebelum BOS  (target ~1:2 RR)
TP2  : Swing high 1h               (target ~1:3.5 RR)
TP3  : Trailing 0.5%

Frekuensi realistis: 1-2x per session di Asia/US window
Win rate target: 65-70% (paling tinggi)
```

### Setup B: CHoCH + FVG Confluence (reversal)

```
Kondisi:
  15m: Downtrend → CHoCH bullish muncul (close di atas swing high terakhir)
  15m: Bullish FVG terbentuk saat gerakan CHoCH (gap di antara 3 candle)
  15m: FVG di Discount Zone 1h
  15m: Harga pullback masuk ke FVG

  TAMBAHAN UNTUK 15m: 1h bias TIDAK boleh strong bearish (no fresh 1h Swing
  BOS bearish dalam 4 candle terakhir). Kalau 1h masih bearish kuat, SKIP B.

Entry: Limit di midpoint FVG
SL   : 0.4% di bawah low FVG
TP1  : Pre-CHoCH swing high
TP2  : Premium zone 1h boundary

Win rate target: 55-60%
WARNING: Ini reversal — risiko lebih tinggi. Skip kalau 4h juga bearish.
```

### Setup C: EQL/EQH Sweep + OB (liquidity grab)

```
Kondisi:
  15m: Ada EQL (atau EQH untuk short) yang jelas
  15m: Harga sweep ke bawah EQL
  15m: Segera setelah sweep, candle balik kuat (body > 60% range candle)
  15m: Bullish Internal OB tepat di area sweep
  15m: Discount Zone 1h

Entry: Market setelah candle balik close di atas EQL
SL   : 0.4% di bawah wick sweep (titik terendah)
TP1  : Swing high terdekat di atas
TP2  : Next OB di atas

Win rate target: 60-65%
LOGIKA: Institusi sengaja sweep retail stops, lalu balik. Kita ikut institusi.
```

---

## Kondisi SKIP — ditambah dari playbook 5m

Selain 7 SKIP rules di playbook original, tambah untuk 15m:

```
❌ Bias 1h dan 4h conflict (4h up, 1h down atau sebaliknya)
   → Probability arah random di 15m → SKIP

❌ ATR(14) di 15m turun > 30% dari rata-rata 24 jam
   → Volatilitas turun = setup A susah develop → SKIP

❌ Funding rate label = EXTREME_LONG atau EXTREME_SHORT
   → Positioning crowded, swing tinggi (positioning unwind) → SKIP

❌ Lewat 30 menit setelah candle 1h pertama session terbuka
   → Tunggu structure 1h confirm dulu → reschedule scan ke 15m berikutnya

❌ Sudah 1 win di session yang sama dan target harian terpenuhi
   → Stop. Don't push your luck.
```

---

## Manajemen sesi harian

**Asia window (00:00-04:00 UTC / 07:00-11:00 WIB):**
- Target: 0-1 trade
- Pair preferensi: pair dengan retail Asia tinggi (HYPE, BNB, XRP, TON, SOL)
- BTC/ETH boleh, tapi setup A lebih sering muncul di pair Asia di window ini

**US window (13:00-17:00 UTC / 20:00-00:00 WIB):**
- Target: 0-1 trade
- Pair preferensi: BTC, ETH, SOL (volume tertinggi)
- Watch out: 30 menit sebelum economic event = PAUSE

**Total target harian:** 1-2 trade. Kalau hari ini cuma 0 trade karena ga
ada Setup A, **itu bagus**. Bukan kerugian. Capital preservation = win.

---

## Akurasi yang realistis (15m + selective)

Per backtest komunitas SMC + 15m timeframe + selective entry:

- **Win rate: 55-65%** (lebih tinggi dari 5m karena selective)
- **RR average: 1:2.2** (15m TP lebih jauh)
- **Trade per minggu: 5-10** (1-2 per hari × 5 hari)
- **Expectancy:** ~+0.5R per trade rata-rata

Yang ngerusak performa (sama dengan playbook 5m, tapi lebih tegas di 15m):
1. Entry intracandle — di 15m fatal, candle bisa balik sebelum close
2. Skip TP1 karena greedy — TP1 50% sacred, ga ada exception
3. Trade saat 1h ranging — ATR rendah = setup gagal
4. Mengabaikan timer 3 jam — "tunggu sebentar lagi" = exit lebih dalam loss
5. Trade di luar window aktif — likuidity rendah = slippage tinggi
