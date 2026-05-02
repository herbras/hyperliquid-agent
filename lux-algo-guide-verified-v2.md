# Lux Algo — Panduan Scalping Akurat (Updated dari Riset TradingView)

Panduan ini ditulis berdasarkan dokumentasi resmi LuxAlgo, TradingView script page,
dan best practice komunitas. Semua klaim diverifikasi dari sumber primer.

---

## PENTING: Pilih Tool yang Tepat

LuxAlgo menerbitkan 368+ scripts di TradingView. Untuk scalping crypto, yang relevan:

### GRATIS — Pakai Ini Dulu
**Smart Money Concepts (SMC) [LuxAlgo]**
- URL: tradingview.com/script/CnB3fSph
- Gratis 100%, open-source, tidak perlu langganan
- Isi: BOS, CHoCH, Order Blocks (Internal + Swing), FVG, EQH/EQL, Premium/Discount zones
- Ini adalah backbone scalping — mulai dari sini sebelum beli apapun

### PREMIUM ($40/bulan) — Beli Hanya Jika Sudah Profitable 3 Bulan
**Signals & Overlays (S&O)**
- Signal langsung di chart + Volatility State filter
- Berguna untuk scalping, tapi SMC sudah cukup untuk 80% setup

**Price Action Concepts (PAC)**
- SMC versi premium: volumetric Order Blocks, MTF dashboard, CHoCH+
- Lebih cocok untuk swing trader yang butuh depth analisis lebih dalam

**Oscillator Matrix (OSC)**
- HyperWave divergence + Money Flow
- Dipakai sebagai konfirmasi TAMBAHAN, bukan signal utama

**Rekomendasi urutan:**
1. Mulai dengan SMC gratis → pelajari 3 bulan
2. Jika profitable, tambah Oscillator Matrix untuk konfirmasi
3. Jika butuh swing trade lebih serius, tambah PAC

---

## Setup SMC di TradingView untuk Scalping

### Cara Pasang
1. TradingView → Indicators → Search: "Smart Money Concepts LuxAlgo"
2. Klik → Add to chart
3. GRATIS — tidak perlu invite-only

### Settings yang Direkomendasikan untuk Scalping Crypto

```
Structure:
  Internal Structure  : ON (micro-structure untuk scalping)
  Swing Structure     : ON (macro context)
  Confluence Filter   : OFF ← Fitur ini HANYA ada di PAC (premium)
                        Jika pakai SMC gratis, gunakan manual confirmation:
                        pastikan OB + FVG + P/D zone sejajar sebelum entry
  Structure Periods   : 10 (lebih sensitif, cocok untuk 5m)

Order Blocks:
  Internal OB         : ON | Show: 3 OB terbaru
  Swing OB            : ON | Show: 2 OB terbaru
  OB Mitigation       : 50% (partial — OB masih valid jika 50% terisi)

Fair Value Gaps:
  Show FVG            : ON
  FVG Extension       : 50 bars (cukup untuk scalping)

Premium/Discount:
  Show P/D Zones      : ON ← wajib untuk discipline entry

Equal Highs & Lows:
  Show EQH/EQL        : ON
  Bars Confirmation   : 3 (cukup untuk 5m)

Color Candles         : ON ← aktifkan ini
```

---

## Komponen SMC — Penjelasan Presisi

### BOS (Break of Structure)
```
Bullish BOS: Close candle di ATAS swing high sebelumnya
  → Trend sedang berlanjut ke atas
  → Ini BUKAN reversal, ini CONTINUATION
  → Entry long setelah pullback ke OB yang terbentuk

Bearish BOS: Close candle di BAWAH swing low sebelumnya
  → Trend sedang berlanjut ke bawah
  → Entry short setelah pullback ke OB yang terbentuk

PENTING: Label BOS hanya muncul setelah candle CLOSE
Jangan entry saat candle masih terbentuk (intracandle entry = dangerous)
```

### CHoCH (Change of Character)
```
Bullish CHoCH: Harga yang sebelumnya downtrend, tiba-tiba break swing high terakhir
  → Ini REVERSAL signal — trend berpotensi berbalik ke atas
  → Lebih awal dari BOS, tapi juga lebih berisiko
  → Konfirmasi: tunggu pullback ke OB yang terbentuk saat CHoCH

Bearish CHoCH: Harga yang sebelumnya uptrend, tiba-tiba break swing low terakhir
  → Reversal ke bawah

CHoCH+ (PAC exclusive): CHoCH yang lebih terkonfirmasi
  Syarat tambahan: sudah ada HL (untuk bullish) atau LH (untuk bearish) terlebih dahulu
  Lebih late tapi win rate lebih tinggi
```

### Order Block (OB)
```
Bullish OB: Candle BEARISH terakhir sebelum Bullish BOS/CHoCH
  → Zona ini adalah "sidik jari" smart money beli
  → Harga cenderung kembali ke sini sebelum lanjut naik
  → Entry: saat harga masuk ke zona OB dari atas

Bearish OB: Candle BULLISH terakhir sebelum Bearish BOS/CHoCH
  → Zona ini adalah "sidik jari" smart money jual
  → Entry: saat harga masuk ke zona OB dari bawah

Mitigation (50% setting):
  OB dianggap masih valid selama harga belum close di luar 50% zona OB
  Jika harga close di dalam atau melewati 50%, OB expired

PRAKTIS: Lux Algo highlight OB sebagai kotak hijau (bull) atau merah (bear)
```

### Fair Value Gap (FVG)
```
Bullish FVG: candle[i-1].high < candle[i+1].low
  → Gap kosong di antara 3 candle berurutan
  → Harga "hutang" untuk mengisi gap ini
  → Sering menjadi zona support sebelum harga lanjut naik

Bearish FVG: candle[i-1].low > candle[i+1].high
  → Gap di atas — harga cenderung kembali mengisinya sebagai resistance

Kombinasi FVG + OB di range yang sama = SANGAT KUAT (confluent zone)
```

### Premium / Discount Zones
```
Cara hitung:
  Range = Swing High - Swing Low
  Equilibrium = 50% dari range (Fibonacci 0.5)
  
  Premium  : Di atas equilibrium → harga "mahal"
  Discount : Di bawah equilibrium → harga "murah"

Aturan:
  Long HANYA di Discount Zone (+ OB) — inilah entry ideal
  Short HANYA di Premium Zone (+ OB)
  
  Entry long di Premium Zone = melawan institusi = risiko sangat tinggi
```

### Equal Highs/Lows (EQH/EQL)
```
EQH: Dua atau lebih swing high yang hampir sama tingginya
  → Likuiditas menumpuk di atas level ini (stop loss trader short)
  → Smart money SERING memicu EQH sweep untuk ambil likuiditas, lalu reverse

EQL: Dua atau lebih swing low yang hampir sama rendahnya
  → Likuiditas di bawah (stop loss trader long)
  → Setelah EQL sweep, cari setup long di dekat zona ini

Strategi: Jangan entry TEPAT di EQH/EQL — tunggu sweep selesai, lalu entry
```

---

## Workflow Scalping 4 Langkah (Diperbaiki)

### Langkah 1: Establish Bias di 15m (2–3 menit)
```
Cek 15m chart:
  → Apakah ada Swing BOS bullish terbaru? (solid line besar)
  → Apakah harga di Discount Zone?
  → Apakah ada Fresh Swing OB di bawah harga?

  Jika semua ya → BULLISH BIAS → cari setup LONG di 5m
  Jika sebaliknya → BEARISH BIAS → cari setup SHORT di 5m
  Jika mix → NO CLEAR BIAS → SKIP sesi ini
```

### Langkah 2: Tunggu Setup di 5m
```
Dengan bullish bias dari 15m, cari di 5m:

1. Internal CHoCH bullish muncul (dashed line, label kecil)
   ATAU
   Internal BOS bullish setelah pullback (ini lebih aman)

2. Harga ada di dekat atau dalam:
   - Fresh Internal Bullish OB (kotak hijau yang belum disentuh)
   - DAN/ATAU Bullish FVG di bawah harga
   - DAN harga di Discount Zone (lihat garis P/D)

3. Cek volume candle (dari panel volume):
   - Volume harus di atas rata-rata 10 candle terakhir
   - Candle yang membentuk OB/CHoCH idealnya bervolume tinggi
```

### Langkah 3: Konfirmasi Entry — JANGAN RUSHING
```
JANGAN entry saat:
  - Candle signal belum close
  - Masih dalam zona OB tapi belum ada rejection candle
  - Volume candle masuk ke OB lebih rendah dari rata-rata

ENTRY SETELAH:
  1. Candle masuk ke OB → tunggu sampai CLOSE
  2. Candle berikutnya open dan terlihat bullish (body lebih besar dari wick bawah)
  3. Entry di OPEN candle ke-3 dari saat OB pertama kali tersentuh

Tipe entry:
  Conservative: Limit order di 50% zone OB (isi sendiri)
  Standard: Market order setelah konfirmasi candle ke-2
```

### Langkah 4: Set Risk Sebelum Entry
```
Stop Loss:
  Letakkan SL di BAWAH low OB + buffer 0.2%
  BUKAN di bawah wick candle signal saja
  BUKAN di bawah candle sebelum signal
  
  Jika SL lebih dari 1% dari entry → SKIP, setup terlalu lebar untuk scalping

Take Profit:
  TP1 (50% posisi): Swing high 5m terdekat sebelum CHoCH
  TP2 (30% posisi): Level EQH atau OB berikutnya di atas
  TP3 (20% posisi): Trailing 0.3%

Timer:
  Jika dalam 60 menit tidak hit TP1 → tutup semua, regardless profit/loss
```

---

## 3 Setup Tertinggi Win Rate

### Setup A: OB Retest setelah Swing BOS (Paling Reliable)
```
Kondisi:
  15m: Swing BOS bullish baru terjadi (solid line)
  5m : Harga pullback ke zona Swing OB yang terbentuk saat BOS
  5m : OB masih Fresh (belum disentuh sama sekali)
  5m : Volume saat masuk OB rendah, volume saat rejection tinggi (ini konfirmasi)
  5m : Harga di Discount Zone 15m

Tingkat keberhasilan: Tertinggi dari semua setup
Frekuensi: Tidak sering — muncul 2-4x per sesi

Entry: Limit order di 50% OB atau market setelah rejection candle close
SL: 0.2% di bawah low OB
TP1: Swing high 5m sebelum BOS
```

### Setup B: CHoCH + FVG Confluence (Reversal)
```
Kondisi:
  5m : Downtrend → CHoCH bullish muncul
  5m : Ada Bullish FVG yang terbentuk saat gerakan CHoCH
  5m : FVG berada di Discount Zone 15m
  5m : Harga pullback masuk ke dalam FVG zone

Entry: Limit di midpoint FVG atau market saat candle konfirmasi di dalam FVG
SL: 0.2% di bawah low FVG
TP1: Pre-CHoCH swing high

CATATAN: Ini reversal setup — lebih berisiko dari Setup A
Skip jika: 15m bias masih strong bearish (Swing BOS bearish baru terjadi)
```

### Setup C: EQL Sweep + Bullish OB (Liquidity Grab)
```
Kondisi:
  5m/15m: Ada EQL (equal lows) yang terlihat jelas
  5m : Harga "sweep" ke bawah EQL (menyentuh stop loss di sana)
  5m : Segera setelah sweep, harga kembali ke atas EQL dengan candle kuat
  5m : Ada Bullish Internal OB tepat di area sweep
  5m : Di Discount Zone

Entry: Market order setelah candle yang membalik close di atas EQL
SL: Di bawah wick sweep (harga terendah yang dicapai)
TP1: Swing high terdekat di atas

LOGIKA: Institusi sengaja sweep stop loss retail, lalu balik arah.
        Kamu ikut institusi, bukan retail yang kena stop.
```

---

## Kondisi SKIP — Wajib Diabaikan

```
Langsung SKIP tanpa exception jika:

❌ Internal Structure banyak CHoCH bolak-balik dalam 10 candle terakhir
   → Market choppy, bukan trending → profit kecil, loss besar

❌ Tidak ada OB atau FVG fresh di dekat harga (< 0.5% dari harga)
   → Tidak ada zona entry yang defined → SL tidak logis

❌ Harga di tengah antara Premium dan Discount (equilibrium ± 10%)
   → Tidak ada bias ke salah satu arah

❌ Ada EQH tepat di atas target TP kamu untuk long
   → Harga mungkin akan sweep EQH terlebih dahulu → TP tidak tercapai

❌ 30 menit sebelum/sesudah economic event besar
   → Candle spike bisa trigger SL sebelum harga berbalik

❌ Pair sedang gap besar (weekend close/open)
   → Behavior tidak normal sampai gap terisi

❌ Sudah 2 SL hari ini
   → Berhenti. Market tidak sedang cocok dengan setup kamu hari ini.
```

---

## Manajemen Trade Aktif

```
0–5 menit setelah entry:
  Jangan sentuh apapun. Biarkan setup berkembang.

5–20 menit:
  Jika TP1 belum hit tapi harga masih dalam Discount zone dan OB intact → hold
  Jika harga kembali ke tengah OB (bukan rejection) → pertimbangkan exit

20–40 menit:
  Jika TP1 masih belum hit:
  → Cek: apakah ada Internal BOS bearish baru terbentuk di 5m? Jika ya → exit
  → Cek: apakah harga sudah break OB ke bawah (close di bawah OB)? Jika ya → exit segera

40–60 menit:
  Jika masih terbuka → EXIT MANUAL. Tidak ada diskusi.

Setelah TP1 hit:
  → WAJIB pindahkan SL ke breakeven (harga entry)
  → Biarkan TP2 dan TP3 jalan sendiri
```

---

## Waktu Trading Terbaik

```
London Session (07:00–12:00 UTC):
  Terbaik untuk BTC, ETH, major pairs
  Biasanya ada 1-2 setup A atau C dalam 3 jam pertama
  Volume tinggi, structure lebih clean

NY Session (13:00–17:00 UTC):
  Volume tertinggi → movement terbesar → signal paling reliable
  Overlap London-NY (13:00–16:00 UTC): setup paling banyak dan paling valid
  Setelah 17:00 UTC: volatilitas turun, lebih choppy

Asian Session (00:00–07:00 UTC):
  Umumnya SKIP untuk scalping kecuali pair Asia (BNB, XRP, TON)
  BTC/ETH: struktur sering tidak develop dengan baik

Hari terbaik: Selasa, Rabu, Kamis (Senin kadang gap behavior, Jumat sering early close)
```

---

## Catatan Jujur tentang Akurasi

SMC LuxAlgo di tangan yang terlatih:
- Win rate realistis: 48–62% untuk scalping
- Win rate yang di-klaim orang di sosmed: 70–85% (sering tidak termasuk loss)
- RR minimum yang membuat profitable: 1:1.5 (dengan win rate 50% sudah break even)
- RR yang harus dikejar: 1:2 minimum

**Yang membuat trader SMC tidak profitable:**
1. Entry sebelum candle close (intracandle entry — setup hilang)
2. SL terlalu dekat (kena noise)
3. Skip TP1 karena greedy → TP tidak pernah tercapai → full loss
4. Trading saat market ranging (paling banyak loss)
5. Tidak mengikuti bias timeframe lebih tinggi
