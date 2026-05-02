---
name: market-data-cron
description: Wrapper untuk 3 fetcher (ccxt generic, Hyperliquid native, Bybit V5 native) — output JSON schema seragam untuk konsumsi agent.
version: 1.1.0
metadata:
  hermes:
    tags: [trading, market-data, cron, ccxt, hyperliquid, bybit]
    category: trading
    requires_toolsets: [terminal]
    config:
      - key: market-data-cron.exchange
        description: "Default fetcher: ccxt | hyperliquid | bybit"
        default: "ccxt"
        prompt: "Fetcher backend"
      - key: market-data-cron.symbols
        description: "Comma-separated symbol list (format depends on backend)"
        default: "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT"
        prompt: "Symbols"
      - key: market-data-cron.timeframe
        description: "Default timeframe (1h untuk bias scan, 15m untuk execution)"
        default: "1h"
        prompt: "Timeframe"
required_environment_variables:
  - name: EXCHANGE
    prompt: ccxt exchange id
    required_for: data fetch
  - name: SYMBOLS
    prompt: ccxt symbol list (comma-separated)
    required_for: data fetch
  - name: TF
    prompt: timeframe (1m, 5m, 15m, 1h, 4h, ...)
    required_for: data fetch
---

# Market Data Cron — fetcher wrapper (3 backend)

Skill ini menjalankan **salah satu** dari 3 fetcher (di-bundle di
panduan-openclaw/hyperliquid/):

| Script | Backend | Symbol format | Funding scale | Catatan |
|---|---|---|---|---|
| `fetch_market_data.py` | ccxt generic (Binance, OKX, Bybit, dst) | `BTC/USDT:USDT` | per-8h | Multi-exchange via single script. Butuh `pip install ccxt`. |
| `fetch_hyperliquid.py` | Hyperliquid native `/info` API | `BTC` (bare coin) | **per-1h** (HL convention) | No deps — stdlib only. Output dapat field `open_interest`. |
| `fetch_bybit.py` | Bybit V5 public API | `BTCUSDT` (no slash) | per-8h | No deps — stdlib only. Field `open_interest` + `category` (linear/inverse/spot). |

Pilih berdasar venue eksekusi:
- **Trade di Bybit** → `fetch_bybit.py` (CEX, deep liquidity, semua pair major)
- **Trade di Hyperliquid** → `fetch_hyperliquid.py` (on-chain perp, HYPE native)
- **Multi-exchange** → `fetch_market_data.py` (ccxt, swap exchange via env)

Output schema **identik** untuk 3-tiganya (lihat di bawah) — scout & sniper
SOUL.md bisa interchange tanpa perubahan kode.

Output schema sama untuk dua-duanya:

```json
{
  "timestamp": ...,
  "timeframe": "15m",
  "symbols": [
    {
      "symbol": "BTC/USDT:USDT",
      "price": 67420.0,
      "funding_rate": 0.0123,
      "funding_label": "LONG_BIAS (0)",
      "ema21": 66980.5,
      "macro_bias": "BULLISH",
      "nearest_fvg": {
        "type": "bull",
        "top": 66950, "bottom": 66890, "mid": 66920,
        "gap_pct": 0.089, "dist_pct": 0.74,
        "status": "fresh"
      },
      "active_fvg_count": 3
    }
  ]
}
```

## When to Use

- Scout profile: cron-driven 15m scan
- Sniper profile: on-demand 5m fetch sebelum confirm setup
- Journal profile: end-of-session price snapshot untuk review

## Procedure

### ccxt generic (`fetch_market_data.py`)
```bash
EXCHANGE=binanceusdm \
SYMBOLS="BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" \
TF=1h \
python3 fetch_market_data.py
```

### Hyperliquid native (`fetch_hyperliquid.py`)
```bash
COINS=BTC,ETH,SOL,HYPE \
TF=1h \
python3 fetch_hyperliquid.py
```

### Bybit V5 native (`fetch_bybit.py`)
```bash
SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT \
CATEGORY=linear \
TF=1h \
python3 fetch_bybit.py
```

Lalu parse stdout JSON, pakai field `macro_bias`, `funding_label`,
`nearest_fvg.dist_pct` untuk klasifikasi GO-LONG / GO-SHORT / SKIP.

## Funding rate label → bias signal

| Label | Crowdedness | Action |
|---|---|---|
| EXTREME_SHORT | Short overcrowded | Contrarian long candidate |
| SHORT_BIAS | Slight short | OK long |
| NEUTRAL | Balanced | Either side OK |
| LONG_BIAS | Slight long | OK short |
| HEAVY_LONG | Long crowded | Contrarian short candidate |
| EXTREME_LONG | Long overcrowded | SKIP long, contrarian short |

## Pitfalls

- Rate limit — semua script sleep antar symbol (0.15-0.5s), tapi kalau >10
  pair, raise limit atau pisah ke 2 cron run.
- FVG dist_pct > 3% di-skip otomatis (terlalu jauh untuk scalping).
- `nearest_fvg=null` artinya tidak ada FVG fresh dalam range — biasanya skip pair.
- **Bybit funding = per-8h, Hyperliquid funding = per-1h.** Threshold di
  `fr_label()` sudah disesuaikan per script — jangan tukar fungsi label
  antar script. Kalau bandingin angka raw `funding_rate`, scale ke unit yang
  sama dulu.
- **Bybit kline list = newest first** (V5 spec). Script auto-reverse jadi
  oldest first sesuai schema. Kalau pakai endpoint lain, perhatikan order.

## Trading execution (separate dari market data)

Skill ini cuma untuk **read** market data publik. Untuk eksekusi trade
ada skill terpisah:

- **Bybit:** install official skill dari https://github.com/bybit-exchange/skills
  — supports HMAC + RSA signing, auto-update, dedicated sub-account workflow.
- **Hyperliquid:** TODO (lihat CATATAN.md) — pakai HL Python SDK dengan
  agent wallet sub-account.

Untuk saat ini, semua eksekusi tetap **manual** — sniper kasih level
(entry/SL/TP), user place order di exchange UI atau API langsung.

## Verification

Cek output ada `error` field per symbol — kalau ada (ccxt error, exchange down),
skip pair tsb dan log warning. Jangan halusinasi data.
