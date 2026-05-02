# Hermes Profiles — Scalping Workflow (15m + Asia/US Window)

3 profile Hermes Agent untuk scalping crypto **15m timeframe** di window
**Asia (00-04 UTC) + US (13-17 UTC)** dengan filosofi **"be good, be wide"**.

> **Baca dulu:**
> - `CATATAN.md` (di folder ini) — overview singkat apa yang sedang dibangun
> - `../STRATEGI-15M.md` — playbook 15m + session windows + filosofi
> - `../lux-algo-guide-verified-v2.md` — playbook original 5m (referensi background)

## Peran tiap profile

| Profile | Peran | Step di playbook |
|---|---|---|
| `scalper-scout` | 15m macro bias scanner. Cron `fetch_market_data.py` (atau `fetch_hyperliquid.py`), kasih shortlist pair + bias + nearest FVG. | Step 1 (Establish Bias di 15m) |
| `scalper-sniper` | 5m setup hunter. User ping dengan pair shortlist, sniper cari Setup A/B/C, hitung entry/SL/TP per playbook, enforce SKIP rules. | Step 2-4 |
| `scalper-journal` | Trade manager & post-mortem. 60-min timer (cron tiap 5min), BE-after-TP1, 2-SL daily stop, end-of-session review. | Manajemen Trade Aktif + Akurasi |

## File scripts (di parent dir `hyperliquid/`)

| Script | Fungsi | Dipakai oleh |
|---|---|---|
| `fetch_market_data.py` | ccxt generic — Binance USDM perps default | scout cron (mode A) |
| `fetch_hyperliquid.py` | Hyperliquid native via `/info` API, no ccxt | scout cron (mode B) |
| `notify_telegram.py` | Helper kirim message ke Telegram chat | scout & journal cron, journal `/halt` |
| `timer_check.py` | Baca `open-positions.json`, output reminder 5/20/40/60 min | journal cron |

## Install (sekali per profile)

```bash
# 1. Buat profile di Hermes
hermes profile create scalper-scout
hermes profile create scalper-sniper
hermes profile create scalper-journal

# 2. Copy config + persona + cron tiap profile
for p in scalper-scout scalper-sniper scalper-journal; do
  cp $p/config.yaml ~/.hermes/profiles/$p/config.yaml
  cp $p/SOUL.md     ~/.hermes/profiles/$p/SOUL.md
  cp $p/.env.example ~/.hermes/profiles/$p/.env  # lalu isi key
  if [ -d $p/cron ]; then
    mkdir -p ~/.hermes/profiles/$p/cron
    cp $p/cron/*.yaml ~/.hermes/profiles/$p/cron/
  fi
done

# 3. State dir untuk journal (open positions)
mkdir -p ~/.hermes/profiles/scalper-journal/state
echo "[]" > ~/.hermes/profiles/scalper-journal/state/open-positions.json

# 4. Skill (shared) — copy ke global skills dir
cp -r shared-skills/lux-algo-smc      ~/.hermes/skills/
cp -r shared-skills/market-data-cron  ~/.hermes/skills/

# 5. Crypto-trader-signals skill (binary skill file)
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

## Mode market data — pilih satu

### Mode A: ccxt generic (default)

Pakai `fetch_market_data.py` + cron `market-scan.yaml`. Default `binanceusdm`,
ganti via env:

```bash
# di ~/.hermes/profiles/scalper-scout/.env
EXCHANGE=binanceusdm
SYMBOLS=BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT
```

Kelebihan: bisa multi-exchange (bybit, okx, dst). Kekurangan: ccxt translasi
funding rate ke 8h-equivalent — perlu perhatikan kalau bandingin sama HL.

### Mode B: Hyperliquid native

Pakai `fetch_hyperliquid.py` + cron `market-scan-hyperliquid.yaml`. Hapus/disable
`market-scan.yaml`, pakai HL variant aja:

```bash
mv ~/.hermes/profiles/scalper-scout/cron/market-scan.yaml \
   ~/.hermes/profiles/scalper-scout/cron/market-scan.yaml.disabled

# di .env:
COINS=BTC,ETH,SOL,HYPE
TF=15m
```

Kelebihan: data langsung dari HL (yang akan kamu trade), termasuk OI per coin
dan funding rate yang akurat untuk venue itu. Kekurangan: cuma HL pairs.

## Pakai harian

```bash
# Scout: cron handle ini otomatis. Manual scan:
scalper-scout chat -q "/scan"

# Sniper: hand-off dari scout
scalper-sniper chat -q "BTC bias bullish, fresh bull FVG 67310-67370. Cari setup A di 5m."

# Journal: lapor entry & exit
scalper-journal chat -q "OPEN: BTC long 67380, SL 67250, TP1 67700, TP2 67950, time=2025-04-30 14:23 UTC"
scalper-journal chat -q "TP1 hit di 14:38"
scalper-journal chat -q "Closed at TP2, +1.4R"

# End of session
scalper-journal chat -q "/daily"

# Emergency stop
scalper-journal chat -q "/halt"   # auto-push notif ke telegram
scalper-journal chat -q "/resume" # besok pagi
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
