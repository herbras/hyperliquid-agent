#!/usr/bin/env python3
"""
Hermes cron data script: Fetch OI, FR, FVG via ccxt untuk analisis trading.

Env config:
  EXCHANGE          single exchange id (default 'binanceusdm')
  EXCHANGE_FALLBACK comma-separated fallback chain — kalau EXCHANGE gagal,
                    coba berikutnya. Contoh: "okx,kucoinfutures,bitget".
                    Pakai ini di VPS yang Bybit/Binance di-block.
  SYMBOLS           comma-separated ccxt symbols
  TF                timeframe (1m, 5m, 15m, 1h, 4h, dst)

Discover working exchange: python3 exchange_picker.py recommend
"""
import asyncio
import json
import sys
import os
import time

# pip install ccxt --break-system-packages
import ccxt.async_support as ccxt


# ── Config ────────────────────────────────────────────────────────────
EXCHANGE_NAME = os.getenv('EXCHANGE', 'binanceusdm')
EXCHANGE_FALLBACK = [x.strip() for x in os.getenv('EXCHANGE_FALLBACK', '').split(',') if x.strip()]
SYMBOLS = os.getenv('SYMBOLS', 'BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT').split(',')
TIMEFRAME = os.getenv('TF', '4h')


# ── FVG Detection ────────────────────────────────────────────────────
def detect_fvg(candles, min_gap_pct=0.001):
    fvgs = []
    for i in range(1, len(candles) - 1):
        c1, c3 = candles[i-1], candles[i+1]
        if c1[2] < c3[3]:
            gap_pct = (c3[3] - c1[2]) / c1[2]
            if gap_pct >= min_gap_pct:
                fvgs.append({
                    'type': 'bull', 'top': round(c3[3], 2),
                    'bottom': round(c1[2], 2),
                    'mid': round((c3[3] + c1[2]) / 2, 2),
                    'gap_pct': round(gap_pct * 100, 3),
                    'status': 'fresh'
                })
        elif c1[3] > c3[2]:
            gap_pct = (c1[3] - c3[2]) / c3[2]
            if gap_pct >= min_gap_pct:
                fvgs.append({
                    'type': 'bear', 'top': round(c1[3], 2),
                    'bottom': round(c3[2], 2),
                    'mid': round((c1[3] + c3[2]) / 2, 2),
                    'gap_pct': round(gap_pct * 100, 3),
                    'status': 'fresh'
                })
    return fvgs


# ── Funding Rate Label ───────────────────────────────────────────────
def fr_label(fr):
    if fr < -0.001:    return 'EXTREME_SHORT (+1)'
    if fr < -0.0005:   return 'SHORT_BIAS (+1)'
    if fr <= 0.0001:   return 'NEUTRAL (0)'
    if fr <= 0.0005:   return 'LONG_BIAS (0)'
    if fr <= 0.001:    return 'HEAVY_LONG (-1)'
    return 'EXTREME_LONG (-1)'


# ── Per-symbol fetch ─────────────────────────────────────────────────
async def fetch_symbol(exchange, symbol):
    candles = await exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=60)
    fr = 0.0
    if exchange.has.get('fetchFundingRate'):
        try:
            funding = await exchange.fetch_funding_rate(symbol)
            fr = funding.get('fundingRate', 0.0) or 0.0
        except Exception:
            pass  # spot exchange / not supported — biarkan 0

    price = candles[-1][4]
    fvgs = detect_fvg(candles)
    active_fvgs = [f for f in fvgs if f['status'] != 'mitigated']
    nearest = None
    if active_fvgs:
        for f in active_fvgs:
            f['dist_pct'] = round(abs(price - f['mid']) / price * 100, 2)
        nearest = min(active_fvgs, key=lambda x: x['dist_pct'])
        if nearest['dist_pct'] > 3.0:
            nearest = None

    closes = [c[4] for c in candles]
    ema21 = closes[0]
    k = 2 / 22
    for c in closes[1:]:
        ema21 = c * k + ema21 * (1 - k)

    return {
        'symbol': symbol,
        'price': round(price, 2),
        'funding_rate': round(fr * 100, 4),
        'funding_label': fr_label(fr),
        'ema21': round(ema21, 2),
        'macro_bias': 'BULLISH' if price > ema21 else 'BEARISH',
        'nearest_fvg': nearest,
        'active_fvg_count': len(active_fvgs),
    }


# ── Main with fallback chain ─────────────────────────────────────────
async def try_exchange(ex_id):
    """Try one exchange; return (results, exchange_used) or (None, None) if fails."""
    if ex_id not in ccxt.exchanges:
        print(f"WARN: '{ex_id}' tidak dikenal di ccxt, skip", file=sys.stderr)
        return None, None
    try:
        exchange = getattr(ccxt, ex_id)({'enableRateLimit': True, 'timeout': 12000})
        await exchange.load_markets()
    except Exception as e:
        print(f"WARN: '{ex_id}' load_markets gagal ({str(e)[:80]}), skip", file=sys.stderr)
        try:
            await exchange.close()
        except Exception:
            pass
        return None, None

    results = []
    for symbol in SYMBOLS:
        symbol = symbol.strip()
        try:
            r = await fetch_symbol(exchange, symbol)
            results.append(r)
        except Exception as e:
            results.append({'symbol': symbol, 'error': str(e)[:120]})
        await asyncio.sleep(0.3)

    await exchange.close()
    return results, ex_id


async def fetch_all():
    chain = [EXCHANGE_NAME] + EXCHANGE_FALLBACK
    seen = set()
    chain = [x for x in chain if not (x in seen or seen.add(x))]  # dedupe

    for ex_id in chain:
        results, used = await try_exchange(ex_id)
        if results is None:
            continue
        # Kalau semua symbol error → coba next exchange
        all_failed = all('error' in r for r in results)
        if all_failed and len(chain) > 1:
            print(f"WARN: '{used}' all symbols failed, trying next in chain",
                  file=sys.stderr)
            continue
        return results, used

    return [{'error': f'all {len(chain)} exchanges failed: {chain}'}], None


if __name__ == '__main__':
    data, used = asyncio.run(fetch_all())
    print(json.dumps({
        'timestamp': int(time.time()),
        'exchange': used,
        'timeframe': TIMEFRAME,
        'symbols': data,
    }, indent=2))