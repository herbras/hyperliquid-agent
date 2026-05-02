# Fetch Economic Calendar (CPI / FOMC / NFP) dari investing.com

Recipe untuk generate `hyperliquid/events.json` — input untuk `pause_check.py`
yang auto-set `PAUSE.flag` 30 menit sebelum CPI/FOMC/NFP.

## Endpoint

```
POST https://www.investing.com/economic-calendar/Service/getCalendarFilteredData
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest
Referer:        https://www.investing.com/economic-calendar/
```

### Body params (form-urlencoded)

| Param | Value | Catatan |
|---|---|---|
| `country[]` | `5` | 5 = United States. Bisa multi: `country[]=5&country[]=4` |
| `importance[]` | `2`, `3` | 1=low, 2=medium, 3=high. Filter high+medium untuk CPI/NFP yang belum di-flag |
| `timeZone` | `55` | 55 = GMT/UTC. Penting biar `release_at` konsisten |
| `timeFilter` | `timeRemain` | wajib |
| `currentTab` | `custom` | atau `today` / `tomorrow` / `nextWeek` |
| `dateFrom` | `2026-05-02` | YYYY-MM-DD |
| `dateTo` | `2026-12-31` | YYYY-MM-DD |
| `submitFilters` | `1` | wajib |
| `limit_from` | `0` | pagination start |

### Response shape

```json
{
  "data": "<HTML string with <tr> rows>",
  "rows_num": 23,
  "dateFrom": "2026/05/02",
  "dateTo": "2026/12/31",
  ...
}
```

`data` field berisi HTML. Parse rows dengan regex (atau BeautifulSoup):

```
<tr id="eventRowId_<int>" ... data-event-datetime="YYYY/MM/DD HH:MM:SS">
  <td>...time...</td>
  <td>... <span title="<Country>" class="ceFlags ...">&nbsp;</span> <CCY> </td>
  <td>... grayFullBullishIcon × N ...</td>
  <td>... <a href="/economic-calendar/<slug>"><name></a> ...</td>
  ...
</tr>
```

- `data-event-datetime` sudah dalam **UTC** (karena `timeZone=55`).
- Jumlah `grayFullBullishIcon` = importance (1-3).
- `<a href>` text = event name.
- Currency code (USD, EUR, dst) ada setelah `</span>` di kolom flag.

## Cara fetch

### Pakai curl (paling simple — endpoint tidak Cloudflare-protected)

```bash
curl -sS -X POST 'https://www.investing.com/economic-calendar/Service/getCalendarFilteredData' \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Referer: https://www.investing.com/economic-calendar/' \
  --data 'country%5B%5D=5&importance%5B%5D=2&importance%5B%5D=3&timeZone=55&timeFilter=timeRemain&currentTab=custom&dateFrom=2026-05-02&dateTo=2026-12-31&submitFilters=1&limit_from=0' \
  -o /tmp/inv.json
```

### Pakai Lightpanda (kalau curl mulai kena 403)

Lihat `cloudflare-bypass.md` — pola `about:blank` + `page.evaluate(fetch)`.

## Parser Python

```python
import json, re
from html import unescape
from datetime import datetime, timezone

d = json.load(open('/tmp/inv.json'))
html = d['data']

row_re = re.compile(
    r'<tr id="eventRowId_(\d+)"[^>]*data-event-datetime="([^"]+)"[^>]*>(.*?)</tr>',
    re.S,
)
ccode_re = re.compile(r'class="ceFlags[^"]*"[^>]*>&nbsp;</span>\s*([A-Z]{3})')
impact_re = re.compile(r'grayFullBullishIcon')
name_re   = re.compile(r'<a href="(/economic-calendar/[^"]+)"[^>]*>\s*([^<]+?)\s*</a>')

def classify(name):
    n = name.lower()
    if 'fed interest rate' in n: return 'FOMC'
    if 'fomc statement' in n or 'fomc press conference' in n: return 'FOMC'
    if 'fomc member' in n and 'speaks' in n: return 'FED_SPEAK'
    if 'nonfarm payroll' in n or 'non-farm payroll' in n: return 'NFP'
    if n.startswith('cpi (yoy)'): return 'CPI'   # headline only, skip Core/MoM
    return None

raw = []
for m in row_re.finditer(html):
    body = m.group(3)
    cc = ccode_re.search(body); nm = name_re.search(body)
    if not (cc and nm and cc.group(1) == 'USD'):
        continue
    name = unescape(nm.group(2)).strip()
    t = classify(name)
    if not t:
        continue
    impact = len(impact_re.findall(body))
    dt = datetime.strptime(m.group(2), '%Y/%m/%d %H:%M:%S').replace(tzinfo=timezone.utc)
    raw.append({
        'id': f"{dt.strftime('%Y-%m-%d')}-{t.lower()}-{m.group(1)}",
        'type': t,
        'release_at': dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'impact': 'high' if impact >= 3 else 'medium' if impact == 2 else 'low',
        'name': name,
        'source': 'investing.com',
        'source_url': 'https://www.investing.com' + nm.group(1),
    })

# Dedupe per (date, type) — keep highest impact
by_key = {}
rank = {'high': 3, 'medium': 2, 'low': 1}
for e in raw:
    k = (e['release_at'][:10], e['type'])
    if k not in by_key or rank[e['impact']] > rank[by_key[k]['impact']]:
        by_key[k] = e

events = sorted(by_key.values(), key=lambda x: x['release_at'])
json.dump(events, open('events.json', 'w'), indent=2)
print(f'wrote {len(events)} events')
```

## Output schema (`events.json`)

```json
[
  {
    "id": "2026-05-08-nfp-546555",
    "type": "NFP",
    "release_at": "2026-05-08T12:30:00Z",
    "impact": "high",
    "name": "Nonfarm Payrolls  (Apr)",
    "source": "investing.com",
    "source_url": "https://www.investing.com/economic-calendar/nonfarm-payrolls-227"
  }
]
```

Type values: `CPI`, `NFP`, `FOMC`, `FED_SPEAK`. Impact: `high`, `medium`,
`low`.

## Caveat penting

- **CPI/NFP cuma muncul ~1 bulan ke depan.** BLS publish exact time + impact
  flag close ke release date. FOMC sudah final 1 tahun ke depan.
- **Refresh mingguan** untuk pickup CPI/NFP bulan berikutnya. Cron contoh:
  `0 6 * * 1` (Senin pagi).
- **Jangan wipe `events.json`** kalau fetch gagal — preserve last good copy
  dan log error ke stderr.
- **`country=5` USD-only.** Untuk EUR (ECB) / JPY (BoJ) tambah country code
  lain (lihat investing.com filter URL).

## Integrasi dengan `pause_check.py`

`pause_check.py` (cron tiap 5 menit) baca `events.json`, hitung jarak ke
event terdekat. Kalau dalam window (`release_at - 30min` s/d
`release_at + 60min`), tulis `~/.hermes/profiles/scalper-journal/PAUSE.flag`.
Scout cek flag ini di awal tiap scan dan auto-skip.

Type FOMC perlu window post-event lebih panjang (120 menit) karena ada press
conference. Configurable per type.
