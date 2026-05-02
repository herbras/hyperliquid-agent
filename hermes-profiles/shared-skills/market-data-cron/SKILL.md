---
name: market-data-cron
description: Wrapper untuk fetch_market_data.py — pull OHLCV+FR+FVG via ccxt, output JSON ringkas untuk konsumsi agent.
version: 1.0.0
metadata:
  hermes:
    tags: [trading, market-data, cron, ccxt]
    category: trading
    requires_toolsets: [terminal]
    config:
      - key: market-data-cron.script_path
        description: "Absolute path ke fetch_market_data.py"
        default: "~/Documents/panduan-openclaw/hyperliquid/fetch_market_data.py"
        prompt: "Path ke fetch_market_data.py"
      - key: market-data-cron.exchange
        description: "ccxt exchange id (binanceusdm, bybit, hyperliquid, dst)"
        default: "binanceusdm"
        prompt: "Exchange id"
      - key: market-data-cron.symbols
        description: "Comma-separated ccxt symbol list"
        default: "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT"
        prompt: "Symbols"
      - key: market-data-cron.timeframe
        description: "Default timeframe (15m untuk scout, 5m untuk sniper)"
        default: "15m"
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

# Market Data Cron — fetcher wrapper (ccxt + Hyperliquid native)

Skill ini menjalankan salah satu dari **dua** fetcher (di-bundle di
panduan-openclaw/hyperliquid/):

- `fetch_market_data.py` — ccxt generic (Binance USDM, Bybit, OKX, dst)
- `fetch_hyperliquid.py` — Hyperliquid native via `/info` API, no ccxt

Pilih berdasar venue: kalau trading di Hyperliquid, pakai HL native (data
match dengan venue, dapat field `open_interest` per coin). Kalau trading di
Binance/CEX lain, pakai ccxt.

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

1. Set env vars: `EXCHANGE`, `SYMBOLS`, `TF`.
2. Run: `python3 {{ skill.config.script_path }}`
3. Parse stdout JSON.
4. Pakai field `macro_bias`, `funding_label`, `nearest_fvg.dist_pct` untuk
   klasifikasi GO-LONG / GO-SHORT / SKIP.

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

- Rate limit — script sleep 0.5s antar symbol, tapi kalau >10 pair, raise limit.
- FVG dist_pct > 3% di-skip otomatis (terlalu jauh untuk scalping).
- `nearest_fvg=null` artinya tidak ada FVG fresh dalam range — biasanya skip pair.

## Verification

Cek output ada `error` field per symbol — kalau ada (ccxt error, exchange down),
skip pair tsb dan log warning. Jangan halusinasi data.
