# Bypass Cloudflare Turnstile dengan Lightpanda

Panduan ini hasil eksperimen real (2026-05-02) di **investing.com** —
agent-browser default (Chromium CDP) **gagal** karena Turnstile detect
headless fingerprint, tapi **Lightpanda lolos**.

## Kapan trick ini relevan

Site target:
- Halaman utama proteksi Cloudflare Turnstile ("Verifikasi bahwa Anda
  adalah manusia" / "Checking your browser…")
- Tapi **endpoint XHR / API**-nya cuma rate-limit, bukan Turnstile-protected.
- Ini umum: investing.com, tradingview, banyak site finance/news.

Cek dulu — banyak endpoint cukup di-curl tanpa browser sama sekali:

```bash
curl -sS -X POST 'https://target.com/api/endpoint' \
  -H 'User-Agent: Mozilla/5.0 ... Chrome/131 ...' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -H 'Referer: https://target.com/' \
  --data 'param=value' -o resp.json -w 'HTTP %{http_code}\n'
```

Kalau curl 200 → STOP, ga perlu Lightpanda. Kalau 403 / Cloudflare HTML
challenge → lanjut step di bawah.

## Resep: `about:blank` + `page.evaluate(fetch)`

**Insight kunci:** Cloudflare Turnstile cek navigator fingerprint hanya
saat **navigate ke halaman yang di-protect**. Kalau page lagi di `about:blank`
dan kita fire `fetch()` ke endpoint XHR target, Turnstile **tidak ke-trigger**
— browser cuma berfungsi sebagai HTTP client dengan JS engine.

Lightpanda fingerprint juga lebih mirip browser real dibanding headless
Chromium default (less canvas/WebGL anomalies), jadi bahkan kalau endpoint
ada light protection, masih lolos.

### Setup

```bash
# 1. Start CDP server
$HOME/.local/bin/lightpanda serve --host 127.0.0.1 --port 9223 \
  > /tmp/lp-serve.log 2>&1 &

# 2. Install playwright-core (sekali)
mkdir -p /tmp/scraper && cd /tmp/scraper
npm install playwright-core
```

### Script template

`fetch-via-lp.js`:

```javascript
const { chromium } = require('/tmp/scraper/node_modules/playwright-core');

(async () => {
  const browser = await chromium.connectOverCDP({
    endpointURL: 'ws://127.0.0.1:9223',
  });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();

  // KEY: stay on about:blank — jangan goto target site utama
  await page.goto('about:blank');

  const result = await page.evaluate(async () => {
    const r = await fetch('https://target.com/api/endpoint', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://target.com/',
      },
      body: 'param=value',
    });
    return { status: r.status, body: await r.text() };
  });

  console.error('status:', result.status);
  process.stdout.write(result.body);

  await page.close();
  await ctx.close();
  await browser.close();
})().catch(e => { console.error('ERR', e); process.exit(1); });
```

Run:

```bash
node fetch-via-lp.js > /tmp/data.json 2> /tmp/data.err
```

## Hasil real (investing.com economic calendar)

| Tool | Result | Bytes |
|---|---|---|
| agent-browser (Chromium CDP) | ❌ Cloudflare challenge wall | n/a |
| `curl` direct | ✅ 200 | 171 KB JSON |
| Lightpanda CDP + `about:blank` trick | ✅ 200 | 171 KB JSON (identik) |

Lihat `fetch-investing-calendar.md` untuk detail recipe.

## Kalau halaman utama-nya BENERAN harus di-load

Beberapa site set cookie session lewat halaman utama, dan endpoint XHR butuh
cookie itu. Dalam case ini, halaman utama harus di-load duluan — tapi
Turnstile akan ke-trigger.

Opsi:

1. **Wait + retry.** Lightpanda kadang lolos Turnstile setelah delay panjang
   (10-30 detik):
   ```javascript
   await page.goto('https://target.com/', { waitUntil: 'load', timeout: 45000 });
   await page.waitForTimeout(15000);  // biarkan CF challenge auto-resolve
   ```
2. **Pre-warm cookies di host browser, copy ke Lightpanda.** Pakai
   `cookies.set()` dengan nilai `cf_clearance` yang sudah valid (didapat
   dari browser real).
3. **Reverse engineer endpoint.** Cek di DevTools real browser — header /
   parameter apa yang sebetulnya wajib. Sering kali cuma butuh `User-Agent`
   yang konsisten + `Referer`.

## Etika & rate limit

- Tetap **hormati rate limit** site target. Lightpanda lolos CF bukan tiket
  untuk hammer endpoint.
- Default cron interval **min 5-15 menit** untuk site finance/news.
- Tambah `User-Agent` yang konsisten + retry-with-backoff. Jangan rotate UA
  acak (justru lebih mudah kena flag).
- Cache hasil — kalau data update tiap jam, jangan fetch tiap menit.

## Limitasi

Lightpanda ga akan lolos:
- **Google reCAPTCHA v3** (heavy fingerprinting)
- **DataDome** / **PerimeterX** (advanced bot detection)
- **Cloudflare advanced bot mode** (kalau site enable Bot Fight Mode + JS
  challenge tier 3)

Untuk site dengan proteksi level itu, perlu solusi lain (residential proxy +
real Chrome profile dengan cookies pre-warmed, atau API resmi).
