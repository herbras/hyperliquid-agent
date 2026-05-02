#!/usr/bin/env python3
"""
Hermes cron data script: Fetch OI, FR, FVG untuk analisis trading.
Stdout dikirim ke agent sebagai context.
"""
import asyncio
import json
import sys
import os

# pip install ccxt --break-system-packages
import ccxt.async_support as ccxt


# ── Config ────────────────────────────────────────────────────────────
EXCHANGE_NAME = os.getenv('EXCHANGE', 'binanceusdm')
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


# ── Main ─────────────────────────────────────────────────────────────
async def fetch_all():
    exchange = getattr(ccxt, EXCHANGE_NAME)({'enableRateLimit': True})
    results = []

    for symbol in SYMBOLS:
        symbol = symbol.strip()
        try:
            candles, funding = await asyncio.gather(
                exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=60),
                exchange.fetch_funding_rate(symbol),
            )

            price = candles[-1][4]
            fr = funding['fundingRate']

            # FVG
            fvgs = detect_fvg(candles)
            active_fvgs = [f for f in fvgs if f['status'] != 'mitigated']
            nearest = None
            if active_fvgs:
                for f in active_fvgs:
                    f['dist_pct'] = round(abs(price - f['mid']) / price * 100, 2)
                nearest = min(active_fvgs, key=lambda x: x['dist_pct'])
                if nearest['dist_pct'] > 3.0:
                    nearest = None

            # EMA untuk macro bias
            closes = [c[4] for c in candles]
            ema21 = closes[0]
            k = 2 / 22
            for c in closes[1:]:
                ema21 = c * k + ema21 * (1 - k)

            results.append({
                'symbol': symbol,
                'price': round(price, 2),
                'funding_rate': round(fr * 100, 4),
                'funding_label': fr_label(fr),
                'ema21': round(ema21, 2),
                'macro_bias': 'BULLISH' if price > ema21 else 'BEARISH',
                'nearest_fvg': nearest,
                'active_fvg_count': len(active_fvgs),
            })
        except Exception as e:
            results.append({'symbol': symbol, 'error': str(e)})

        await asyncio.sleep(0.5)

    await exchange.close()
    return results


if __name__ == '__main__':
    data = asyncio.run(fetch_all())
    print(json.dumps({
        'timestamp': asyncio.get_event_loop().time(),
        'timeframe': TIMEFRAME,
        'symbols': data,
    }, indent=2))