# Hermes Profiles — Scalping Workflow (15m + Asia/US Window)

3 profile Hermes Agent untuk scalping crypto **15m timeframe** di window
**Asia (00-04 UTC) + US (13-17 UTC)** dengan filosofi **"be good, be wide"**.

> **Baca dulu:**
> - `CATATAN.md` (di folder ini) — overview singkat apa yang sedang dibangun
> - `../STRATEGI-15M.md` — playbook 15m + session windows + filosofi
> - `../lux-algo-guide-verified-v2.md` — playbook original 5m (referensi background)

## Peran tiap profile (4 agent)

| Profile | Peran | Trigger |
|---|---|---|
| `scalper-scout` | 1h bias scanner — fire alert hanya saat ada GO-LONG/SHORT di Setup A candidate | Cron tiap 15min, Asia + US window |
| `scalper-sniper` | 15m setup hunter — hitung entry/SL/TP, enforce 9 aturan SKIP | Manual chat saat scout fire |
| `scalper-journal` | Trade manager — `position_write.py` auto-track, timer 3 jam, BE rule, 2-SL halt | Cron tiap 5min (timer-check), manual on entry/exit |
| **`scalper-coach`** | **Knowledge-based coach — baca KB + history, kasih briefing/debrief/weekly review, auto-PAUSE event window** | **Cron: pre-session (12:30/23:30 UTC), debrief (04:15/17:15 UTC), weekly (Jum 17:30 UTC), event-watch tiap 10min** |

## File scripts (di parent dir `hyperliquid/`)

| Script | Fungsi | Dipakai oleh |
|---|---|---|
| `fetch_market_data.py` | ccxt generic — Binance/OKX/Bybit/dst | scout cron (mode A) |
| `fetch_hyperliquid.py` | Hyperliquid native via `/info` API, no ccxt | scout cron (mode B) |
| `fetch_bybit.py` | Bybit V5 public API, no ccxt | scout cron (mode C) |
| `notify_telegram.py` | Helper kirim message ke Telegram chat | semua cron + `/halt` `/resume` |
| `timer_check.py` | Baca `open-positions.json`, reminder 15/60/120/180 min | journal cron |
| `position_write.py` | Parse natural language → tulis ke open-positions.json + history | journal SOUL invocation |
| `economic_calendar.py` | Fetch ForexFactory calendar, auto set/unset PAUSE.flag | coach cron event-watch |
| `backtest_15m.py` | MVP backtest Setup A (long only) di 15m, validate strategi | manual `python3 backtest_15m.py BTC 30 hl` |

## Install (sekali per profile)

```bash
# 1. Buat 4 profile di Hermes
for p in scalper-scout scalper-sniper scalper-journal scalper-coach; do
  hermes profile create $p
done

# 2. Copy config + persona + cron tiap profile
for p in scalper-scout scalper-sniper scalper-journal scalper-coach; do
  cp $p/config.yaml ~/.hermes/profiles/$p/config.yaml
  cp $p/SOUL.md     ~/.hermes/profiles/$p/SOUL.md
  cp $p/.env.example ~/.hermes/profiles/$p/.env  # lalu isi key
  if [ -d $p/cron ]; then
    mkdir -p ~/.hermes/profiles/$p/cron
    cp $p/cron/*.yaml ~/.hermes/profiles/$p/cron/
  fi
done

# 3. State dir untuk journal — open positions, history, lessons
mkdir -p ~/.hermes/profiles/scalper-journal/state
echo "[]" > ~/.hermes/profiles/scalper-journal/state/open-positions.json
touch ~/.hermes/profiles/scalper-journal/state/trade-history.jsonl
cp scalper-journal/state-template/LESSONS.md \
   ~/.hermes/profiles/scalper-journal/state/LESSONS.md

# 4. Skills (shared) — 4 skill ke global dir
cp -r shared-skills/lux-algo-smc         ~/.hermes/skills/
cp -r shared-skills/market-data-cron     ~/.hermes/skills/
cp -r shared-skills/scalper-knowledge    ~/.hermes/skills/
cp -r shared-skills/lightpanda-scrape    ~/.hermes/skills/

# 4b. Install Lightpanda binary (untuk scraping CF-protected sites,
#     contoh: investing.com economic calendar untuk auto-PAUSE.flag)
curl -fsSL https://pkg.lightpanda.io/install.sh | bash
# Lihat shared-skills/lightpanda-scrape/references/install-on-server.md
# untuk PATH setup, systemd unit, MCP setup, troubleshooting.

# 5. Crypto-trader-signals skill (binary)
hermes skill install ../crypto-trader-signals-v4.skill
```

## Telegram setup

1. Chat `@BotFather` di Telegram → `/newbot` → dapat token.
2. Send pesan apa saja ke bot baru → buka `https://api.telegram.org/bot<TOKEN>/getUpdates` → lihat `chat.id`. (Atau pakai `@userinfobot`.)
3. Isi di **semua tiga** `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABCdef...
   TELEGRAM_CHAT_ID=987654321
   ```
4. Test dari journal:
   ```
   scalper-journal chat -q "/test-tg"
   ```
   Harus muncul di chat: `📱 Telegram test from scalper-journal — ...`

## Mode market data — pilih satu (atau aktifkan multiple)

3 mode tersedia. Pilih berdasar venue eksekusi. Bisa juga aktifkan 2 cron
untuk monitor 2 venue paralel (Bybit + HL).

### Mode A: ccxt generic (multi-exchange via single script)

Pakai `fetch_market_data.py` + cron `market-scan.yaml`. Default
`binanceusdm`, swap via env:

```bash
# di ~/.hermes/profiles/scalper-scout/.env
EXCHANGE=binanceusdm     # atau bybit, okx, dst
SYMBOLS=BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT
TF=1h
```

Kelebihan: switch exchange via env saja. Kekurangan: butuh `pip install ccxt`,
funding rate format depends on exchange (perhatikan saat compare).

### Mode B: Hyperliquid native (recommended kalau trade di HL)

Pakai `fetch_hyperliquid.py` + cron `market-scan-hyperliquid.yaml`:

```bash
mv ~/.hermes/profiles/scalper-scout/cron/market-scan.yaml \
   ~/.hermes/profiles/scalper-scout/cron/market-scan.yaml.disabled

# di .env:
COINS=BTC,ETH,SOL,HYPE,XRP
TF=1h
```

Kelebihan: data langsung dari venue eksekusi (HL), `open_interest` per coin,
funding rate per-1h (HL convention). Kekurangan: cuma HL pairs (tidak ada
pair Asia retail kayak BNB/TON di HL).

### Mode C: Bybit V5 native (recommended kalau trade di Bybit)

Pakai `fetch_bybit.py` + cron `market-scan-bybit.yaml`. Bybit dan
Hyperliquid sama-sama best pilihan untuk perp trading — pilih atau pakai
keduanya:

```bash
mv ~/.hermes/profiles/scalper-scout/cron/market-scan.yaml \
   ~/.hermes/profiles/scalper-scout/cron/market-scan.yaml.disabled

# di .env:
SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT
CATEGORY=linear   # linear (USDT/USDC perp) | inverse | spot
TF=1h
```

Kelebihan: deep liquidity CEX, semua pair major, `open_interest` per pair,
funding rate per-8h (Bybit convention). Kekurangan: bukan on-chain native.

**Untuk eksekusi trade di Bybit (future)**, install official AI Skill:

```bash
git clone https://github.com/bybit-exchange/skills ~/.hermes/skills/bybit-trading
# atau via Hermes:
hermes skill install https://github.com/bybit-exchange/skills
```

Skill ini auto-update, support HMAC + RSA signing, dedicated sub-account
workflow. Setup `.env` dengan `BYBIT_API_KEY` + `BYBIT_API_SECRET` (Read +
Trade only, NEVER Withdraw). Lihat README Bybit skill untuk detail.

> **Saat ini sniper masih kasih level secara manual** — eksekusi via Bybit
> skill belum di-wire ke sniper SOUL. Tracked di `CATATAN.md` TODO list.

## Pakai harian

```bash
# === SCOUT (cron auto, manual fallback) ===
scalper-scout chat -q "/scan"

# === SNIPER (manual saat scout fire) ===
scalper-sniper chat -q "BTC bias bullish 1h, fresh bull FVG 67310-67370. Cari setup A di 15m."

# === JOURNAL (entry/exit tracking) ===
scalper-journal chat -q "OPEN: BTC long 67380, SL 67110, TP1 67980, TP2 68450"
scalper-journal chat -q "TP1 hit"          # auto move-be
scalper-journal chat -q "TP2 hit, closed"  # auto compute R, append history
scalper-journal chat -q "/pos-stats"       # daily stats
scalper-journal chat -q "/halt"            # emergency 2-SL stop

# === COACH (mostly cron, manual ad-hoc) ===
scalper-coach chat -q "/brief"             # pre-session briefing
scalper-coach chat -q "/debrief"           # post-session debrief
scalper-coach chat -q "/weekly"            # weekly review (Jumat)
scalper-coach chat -q "/ask kapan harus skip Setup B?"   # KB query
scalper-coach chat -q "/upcoming"          # economic events 24h
scalper-coach chat -q "/stats"             # week stats

# === BACKTEST (manual, validate strategi) ===
python3 ../backtest/backtest_15m.py BTC 30 hl       # 30 hari Hyperliquid
python3 ../backtest/backtest_15m.py SOL 14 ccxt     # 14 hari Binance
```

## Yang HARUS di-set sebelum jalan

1. `.env` tiap profile: `ANTHROPIC_API_KEY`, `HL_REPO`, `TELEGRAM_*`.
2. Pilih mode A atau B (bukan dua-duanya aktif bersamaan — duplikat alert).
3. Cron schedule timezone — default `UTC`, sesuaikan di `cron/*.yaml` kalau
   perlu. London 07-12 UTC, NY 13-17 UTC adalah default sweet-spot per playbook.
4. Inspect file di `state/` setelah hari pertama — pastikan `open-positions.json`
   ke-update dengan format yang `timer_check.py` baca.

## Memilih model

Default `anthropic/claude-sonnet-4-6` di tiga profile. Kalau mau lebih murah
untuk scout (tugasnya mekanis), set:

```bash
scalper-scout config set model.default anthropic/claude-haiku-4-5-20251001
```

Untuk sniper, **jangan turunkan** ke haiku — confluence reasoning butuh sonnet
minimal. Untuk journal, sonnet juga preferred (post-mortem lebih useful).
