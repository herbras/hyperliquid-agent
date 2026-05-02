# Hyperliquid Scalping System

Sistem scalping crypto 15m dengan filosofi **"be good, be wide"** — Asia +
US window only, 4 agent Hermes proaktif, dual-venue support (Bybit +
Hyperliquid).

## Quick start

```bash
git clone git@github.com:herbras/hyperliquid-agent.git ~/Documents/hyperliquid
cd ~/Documents/hyperliquid

# Set repo path (cron yaml default-nya ke path lain — override pakai env)
export HL_REPO=~/Documents/hyperliquid

# Install agent + cron (lihat hermes-profiles/README.md)
# Sebagian besar script stdlib-only; cuma fetch_market_data.py butuh `pip install ccxt`.
```

> Repo ini standalone, tapi dipakai dari dalam `panduan-openclaw/` via
> symlink. Path default di cron yaml masih
> `~/Documents/panduan-openclaw/hyperliquid` — kalau struktur kamu beda,
> override `HL_REPO` di shell env atau di file cron.

## Quick map

| Mau apa? | Lihat |
|---|---|
| Pahami strategi & filosofi | `STRATEGI-15M.md` |
| Pahami arsitektur sistem | `hermes-profiles/CATATAN.md` |
| Install agent + cron | `hermes-profiles/README.md` |
| Background SMC concept | `lux-algo-guide-verified-v2.md` |

## Struktur kode

```
hyperliquid/
├── README.md                       ← kamu sedang di sini
├── STRATEGI-15M.md                 ← playbook canonical
├── lux-algo-guide-verified-v2.md   ← background SMC (5m original)
├── crypto-trader-signals-v4.skill  ← binary skill artifact
│
├── data/        # market data fetchers (read-only, no auth)
├── trade/       # order execution (HIGH-STAKES, dry-run default)
├── journal/     # position state management
├── events/      # economic calendar + PAUSE.flag
├── notify/      # Telegram alert helper
├── backtest/    # strategy validation
│
└── hermes-profiles/   # 4 agent definition (scout/sniper/journal/coach)
```

## Tiap subdir, satu domain — keep it focused

### `data/` — Market data fetchers

3 fetcher (schema output **identik**) + 1 discovery tool:

```bash
SYMBOLS=BTCUSDT,ETHUSDT TF=1h python3 data/fetch_bybit.py        # Bybit V5 native
COINS=BTC,ETH,SOL,HYPE TF=1h  python3 data/fetch_hyperliquid.py  # HL native
EXCHANGE=htx EXCHANGE_FALLBACK=gate,kucoinfutures \
SYMBOLS=BTC/USDT TF=1h python3 data/fetch_market_data.py         # ccxt generic
```

`fetch_market_data.py` sekarang support **fallback chain** — kalau exchange
pertama gagal/blocked, otomatis coba berikutnya.

**Discover preferred exchange** — pakai untuk pilih sumber data analisis:

```bash
python3 data/exchange_picker.py list           # 14 exchange populer + feature matrix
python3 data/exchange_picker.py test           # reachability test (curated)
python3 data/exchange_picker.py test --all     # test SEMUA 100+ ccxt exchanges
python3 data/exchange_picker.py info okx       # capability & timeframes
python3 data/exchange_picker.py try okx --pair BTC/USDT --tf 15m  # live sample
python3 data/exchange_picker.py recommend      # rank + suggested EXCHANGE_FALLBACK
```

Berguna saat:
- Pindah ke VPS yang region-blocked (Binance/Bybit) → cari alternatif (HTX, Gate, KuCoin)
- Cari exchange dengan pair tertentu (small-cap altcoins)
- Compare liquidity / spread / capabilities antar exchange

Lihat `hermes-profiles/shared-skills/market-data-cron/SKILL.md` untuk schema.

### `trade/` — Order execution (Bybit)

```bash
python3 trade/bybit_execute.py preflight                  # always run first
python3 trade/position_size.py --pair BTCUSDT \
  --entry 67380 --sl 67110 --side long --risk 1.0         # qty calc
python3 trade/bybit_execute.py place \
  --pair BTCUSDT --side long --qty 0.01 \
  --entry 67380 --sl 67110 --tp1 67980                     # DRY-RUN default
```

Real order butuh **dua barrier**: `BYBIT_DRY_RUN=0` env + `--confirm` flag.
Hyperliquid execution = TODO (lihat CATATAN.md).

### `journal/` — Position state

```bash
python3 journal/position_write.py open "BTC long 67380, SL 67110, TP1 67980"
python3 journal/position_write.py move-be BTC
python3 journal/position_write.py close BTC tp2
python3 journal/position_write.py stats today
python3 journal/timer_check.py                            # cron tiap 5min
```

State di `~/.hermes/profiles/scalper-journal/state/`:
- `open-positions.json` — posisi aktif
- `trade-history.jsonl` — closed trades, append-only
- `LESSONS.md` — knowledge yang tumbuh, di-append coach

### `events/` — Economic calendar

```bash
# Cron weekly: refresh events.json dari investing.com
python3 hermes-profiles/shared-skills/lightpanda-scrape/scripts/scrape_investing_calendar.py

# Cron tiap 5 menit: cek window pause, set/unset PAUSE.flag
python3 events/pause_check.py
```

Window pause: CPI/NFP −30/+60min, FOMC −30/+120min, FED_SPEAK −15/+30min.

### `notify/` — Telegram

```bash
echo "alert" | python3 notify/notify_telegram.py
python3 notify/notify_telegram.py "BTC GO-LONG"
```

Auto-chunk message > 4000 char, MarkdownV2 escape (preserve code blocks).

### `backtest/` — Validation

```bash
python3 backtest/backtest_15m.py BTC 30 hl     # 30 hari Hyperliquid
python3 backtest/backtest_15m.py SOL 14 ccxt   # 14 hari Binance
```

Output: WR, total R, distribusi exit reason vs target STRATEGI-15M.md
(55-65% WR, +0.4 avg R).

## Pakai script standalone vs via Hermes profile

Semua script bisa jalan standalone (test, debug, ad-hoc query). Di sistem
production, **dijalankan via cron yang di-define di profile**. Profile yang
schedule kapan jalan, parse output, kirim Telegram, dst.

Lihat `hermes-profiles/README.md` untuk install + pakai-harian.

## Conventions

- **All scripts: stdlib only**, kecuali `data/fetch_market_data.py` yang
  butuh `ccxt`. Reason: low friction install, cron-friendly.
- **Path env: `HL_REPO`** — semua cron yaml pakai `${HL_REPO}/SUBDIR/script.py`.
  Default `~/Documents/panduan-openclaw/hyperliquid`.
- **Schema seragam** untuk fetcher: `{symbol, price, funding_rate,
  funding_label, ema21, macro_bias, nearest_fvg, ...}`. Scout/sniper SOUL
  tidak perlu beda per venue.
- **State terpisah dari source.** Source di `hyperliquid/`, runtime state
  di `~/.hermes/profiles/scalper-*/state/`.
