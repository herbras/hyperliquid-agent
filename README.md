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

# Install Python deps yang dibutuhkan beberapa script
pip install --user --break-system-packages \
  ccxt \
  telethon \
  hyperliquid-python-sdk eth-account

# Install agent + cron (lihat hermes-profiles/README.md)
```

Script per-dependency map:

| Script | Dep | Reason |
|---|---|---|
| `data/fetch_market_data.py`, `data/exchange_picker.py` | `ccxt` | Multi-exchange unified API |
| `data/fetch_telegram_feed.py` | `telethon` | Telegram MTProto client |
| `trade/hyperliquid_execute.py` | `hyperliquid-python-sdk` + `eth-account` | EIP-712 signing |
| Sisanya (`fetch_hyperliquid.py`, `fetch_bybit.py`, `notify_telegram.py`, `bybit_execute.py`, `position_write.py`, `timer_check.py`, `pause_check.py`, `economic_calendar.py`, `position_size.py`, `backtest_*.py`) | stdlib only | No deps |

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
├── data/        # market data + telegram news + picker (6 scripts)
├── trade/       # order execution Bybit + HL (3 scripts, dry-run default)
├── journal/     # position state + timer (2 scripts)
├── events/      # economic calendar + PAUSE.flag (2 scripts)
├── notify/      # Telegram alert helper (1 script)
├── backtest/    # strategy validation (2 scripts)
│
└── hermes-profiles/   # 4 agent definition (scout/sniper/journal/coach)
```

## Tiap subdir, satu domain — keep it focused

### `data/` — Market data + news fetchers

3 market fetcher (schema output **identik**) + telegram feed + discovery tool +
combined wrapper:

```bash
# Market data — pilih satu venue
SYMBOLS=BTCUSDT,ETHUSDT TF=1h python3 data/fetch_bybit.py        # Bybit V5 native
COINS=BTC,ETH,SOL,HYPE TF=1h  python3 data/fetch_hyperliquid.py  # HL native
EXCHANGE=htx EXCHANGE_FALLBACK=gate,kucoinfutures \
SYMBOLS=BTC/USDT TF=1h python3 data/fetch_market_data.py         # ccxt + fallback chain

# Telegram channel feed (fundamental news context)
python3 data/fetch_telegram_feed.py --channel marketfeed --hours 4 --limit 8

# Combined wrapper — market + news, dipakai cron market-scan*.yaml
DATA_SOURCE=hl COINS=BTC,ETH,SOL,HYPE \
  python3 data/scan_with_feed.py
```

`fetch_market_data.py` support **fallback chain** — kalau exchange pertama
gagal/blocked, auto-coba berikutnya. `scan_with_feed.py` graceful-degrade
kalau telegram credentials belum di-set.

**Discover preferred exchange** — `data/exchange_picker.py`:

```bash
python3 data/exchange_picker.py list           # 14 exchange populer + matrix
python3 data/exchange_picker.py test           # reachability test (curated)
python3 data/exchange_picker.py test --all     # test SEMUA 100+ exchanges
python3 data/exchange_picker.py info okx       # capabilities & timeframes
python3 data/exchange_picker.py try okx --pair BTC/USDT --tf 15m
python3 data/exchange_picker.py recommend      # rank + suggested EXCHANGE_FALLBACK
```

Berguna saat:
- Pindah ke VPS yang region-blocked (Binance/Bybit) → cari alternatif (HTX, Gate, KuCoin)
- Cari exchange dengan pair tertentu (small-cap altcoins)
- Compare liquidity / spread / capabilities antar exchange

**Telegram setup (sekali)** untuk `fetch_telegram_feed.py`:
1. Get `api_id` + `api_hash` di https://my.telegram.org/apps
2. Set `TELEGRAM_API_ID` + `TELEGRAM_API_HASH` di `~/.hermes/.env`
3. Run `python3 data/fetch_telegram_feed.py --setup` (interactive, butuh phone + SMS code)

Lihat `hermes-profiles/shared-skills/market-data-cron/SKILL.md` untuk schema.

### `trade/` — Order execution (Bybit + Hyperliquid)

Dual venue, sama-sama dry-run default. Real order butuh **dua barrier**:
env `*_DRY_RUN=0` + flag `--confirm`.

**Bybit V5 (HMAC):**
```bash
python3 trade/bybit_execute.py preflight                  # clock + key + perms check
python3 trade/position_size.py --pair BTCUSDT \
  --entry 67380 --sl 67110 --side long --risk 1.0         # qty calc dari risk %
python3 trade/bybit_execute.py place \
  --pair BTCUSDT --side long --qty 0.01 \
  --entry 67380 --sl 67110 --tp1 67980                     # DRY-RUN default
```

**Hyperliquid (EIP-712 via agent wallet):**
```bash
python3 trade/hyperliquid_execute.py preflight            # main vs agent address check
python3 trade/hyperliquid_execute.py place \
  --coin BTC --side long --qty 0.01 \
  --entry 67380 --sl 67110 --tp1 67980                     # DRY-RUN default
python3 trade/hyperliquid_execute.py position --coin BTC
python3 trade/hyperliquid_execute.py cancel-all --coin BTC
```

Setup HL agent wallet (sekali): app.hyperliquid.xyz → Settings → API →
"Authorize API Wallet" → save agent private key di `.env`. Preflight
otomatis refuse kalau agent address derive ke main wallet (safety guard).

Pair format beda: Bybit `BTCUSDT`, HL `BTC` (no /USDC). Setup default per
`STRATEGI-15M.md`: HL untuk pair on-chain native (HYPE), Bybit untuk pair
major (BTC/ETH/SOL).

### `journal/` — Position state

```bash
python3 journal/position_write.py open "BTC long 67380, SL 67110, TP1 67980"
python3 journal/position_write.py move-be BTC
python3 journal/position_write.py close BTC tp2
python3 journal/position_write.py stats today            # cron 23:50 UTC daily
python3 journal/timer_check.py                            # cron tiap 5min
```

State di `~/.hermes/profiles/scalper-journal/state/`:
- `open-positions.json` — posisi aktif
- `trade-history.jsonl` — closed trades, append-only
- `LESSONS.md` — knowledge yang tumbuh, di-append coach

### `events/` — Economic calendar + auto-PAUSE

```bash
# Source 1: Investing.com (USD CPI/NFP/FOMC/FED_SPEAK, paling reliable)
# Cron weekly Senin 06:00 UTC: refresh events.json
python3 hermes-profiles/shared-skills/lightpanda-scrape/scripts/scrape_investing_calendar.py

# Source 2: ForexFactory (legacy fallback, bundled di stdlib)
python3 events/economic_calendar.py upcoming 24
python3 events/economic_calendar.py force-pause 30

# Cron tiap 5 menit: baca events.json, set/unset PAUSE.flag berdasar window
python3 events/pause_check.py
python3 events/pause_check.py --status   # info-only, no flag mutation
```

Window pause auto-managed: CPI/NFP −30/+60min, FOMC −30/+120min,
FED_SPEAK −15/+30min. Saat PAUSE.flag aktif, scout & sniper refuse trade.

### `notify/` — Telegram

```bash
echo "alert" | python3 notify/notify_telegram.py
python3 notify/notify_telegram.py "BTC GO-LONG"
```

Auto-chunk message > 4000 char, MarkdownV2 escape (preserve code blocks).

### `backtest/` — Validation

```bash
# Single pair, 3 setup (A/B/C), output report
python3 backtest/backtest_15m.py BTC 30 hl              # 30 hari Hyperliquid
python3 backtest/backtest_15m.py SOL 14 ccxt            # 14 hari ccxt
python3 backtest/backtest_15m.py BTC 30 hl --setup A    # Setup A only
python3 backtest/backtest_15m.py SOL 60 hl --setup B,C  # B & C

# Multi-pair × 3 setup × N hari, pivot table dengan verdict per cell
python3 backtest/multi_pair.py 30 BTC ETH SOL HYPE
```

Output: WR, total R, distribusi exit reason vs target STRATEGI-15M.md
(55-65% WR, +0.4 avg R). Pivot menandai per cell: HIT TARGET / LOSING /
MARGINAL biar gampang spot pair-setup yang profitable.

## Pakai script standalone vs via Hermes profile

Semua script bisa jalan standalone (test, debug, ad-hoc query). Di sistem
production, **dijalankan via cron yang di-define di profile**. Profile yang
schedule kapan jalan, parse output, kirim Telegram, dst.

Lihat `hermes-profiles/README.md` untuk install + pakai-harian.

## Conventions

- **Stdlib first, third-party hanya kalau perlu.** Lihat per-script dep
  table di atas. Sebagian besar pakai `urllib`/`json`/`asyncio` saja.
- **Path env: `HL_REPO`** — semua cron yaml pakai `${HL_REPO}/SUBDIR/script.py`.
  Default `~/Documents/panduan-openclaw/hyperliquid`.
- **Schema seragam** untuk fetcher: `{symbol, price, funding_rate,
  funding_label, ema21, macro_bias, nearest_fvg, ...}`. Scout/sniper SOUL
  tidak perlu beda per venue.
- **State terpisah dari source.** Source di `hyperliquid/`, runtime state
  di `~/.hermes/profiles/scalper-*/state/`.
- **Dry-run default** untuk semua operasi destructive (place order,
  cancel-all, halt). Real action butuh dua barrier eksplisit (env + flag).
- **Graceful degrade** untuk dependency runtime — kalau ccxt belum install
  / telegram belum auth / Bybit IP-blocked, script fallback ke alternatif
  atau skip dengan reason jelas (bukan crash).
