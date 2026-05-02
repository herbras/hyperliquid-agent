---
name: lightpanda-scrape
description: Headless browser (Lightpanda) untuk scraping data dari site yang diproteksi Cloudflare / butuh JS exec — alternatif Chrome/Chromium yang 9x lebih cepat & 16x lebih ringan. Cocok untuk fetch economic calendar, market data web, data ekstraksi tanpa render UI.
version: 1.0.0
metadata:
  hermes:
    tags: [scraping, browser, automation, cloudflare, web-data]
    category: data-fetch
    requires_toolsets: [terminal]
    config:
      - key: lightpanda-scrape.binary_path
        description: "Absolute path ke binary lightpanda"
        default: "$HOME/.local/bin/lightpanda"
        prompt: "Path binary"
      - key: lightpanda-scrape.cdp_port
        description: "Port default untuk CDP serve mode"
        default: "9223"
        prompt: "CDP port"
---

# Lightpanda Scrape — headless browser untuk data fetch

Gunakan saat:
- Site target proteksi **Cloudflare Turnstile** dan agent-browser/Chromium
  default kena block.
- Butuh **eksekusi JS** (SPA, XHR-loaded data) — `curl` doang ga cukup.
- Butuh footprint kecil di server (Lightpanda ~16x lebih hemat memory dari
  Chromium, start instant).

Jangan gunakan kalau:
- Endpoint udah JSON/REST plain — pakai `curl` / `urllib` langsung.
- Butuh render visual (screenshot, PDF, video) — pakai full Chromium.
- Site pasang **Google reCAPTCHA v3** atau anti-bot fingerprint berat —
  Lightpanda ga akan lolos itu.

## Install (sekali per server)

```bash
curl -fsSL https://pkg.lightpanda.io/install.sh | bash
```

Binary terpasang di `$HOME/.local/bin/lightpanda`. Pastikan `$HOME/.local/bin`
masuk `PATH`. Verify:

```bash
$HOME/.local/bin/lightpanda --help | head -3
# usage: lightpanda command [options] [URL]
```

Lengkap: lihat `references/install-on-server.md` (Ubuntu, Debian, macOS,
systemd unit, troubleshooting binary release).

## 3 mode pemakaian

| Mode | Untuk apa | Komentar |
|---|---|---|
| **`fetch` (CLI)** | One-shot dump halaman publik (HTML / markdown / semantic tree) | Paling simple, no daemon |
| **`serve` (CDP)** | Multi-step navigation, eksekusi XHR dari page context, bypass CF challenge | Perlu node + `playwright-core` atau `puppeteer-core` |
| **`mcp`** | Workflow agentic via MCP tools (`goto`, `click`, `fill`, `evaluate`) | Setup MCP server di config Claude Code |

### Mode 1 — CLI fetch (paling cepat)

```bash
lightpanda fetch \
  --dump markdown \
  --wait-until networkidle \
  --wait-ms 10000 \
  https://example.com/page
```

`--dump` opsi: `html` | `markdown` | `semantic_tree` | `semantic_tree_text`.
Tambah `--strip-mode js,css,ui` untuk buang noise. Output ke stdout.

### Mode 2 — CDP serve + script (untuk Cloudflare bypass)

```bash
# 1. Start CDP server (background)
lightpanda serve --host 127.0.0.1 --port 9223 > /tmp/lp.log 2>&1 &

# 2. Connect dari Node script via playwright-core
node fetch-via-cdp.js
```

Trick penting untuk **bypass Cloudflare Turnstile**:
**jangan navigate ke halaman Turnstile-protected**, cukup `goto('about:blank')`
lalu `page.evaluate()` panggil endpoint XHR target. Cloudflare cuma cek
fingerprint saat halaman utama di-load — endpoint API biasanya cuma rate-limit,
tidak Turnstile-protected.

Lengkap: lihat `references/cloudflare-bypass.md` (resep + script siap-pakai).

### Mode 3 — MCP server

```bash
claude mcp add lightpanda -- $HOME/.local/bin/lightpanda mcp
```

Lalu agent bisa pakai tool `goto`, `markdown`, `evaluate`, `click`, `fill`,
`waitForSelector` langsung. Cocok untuk eksplorasi interaktif. Bukan pilihan
untuk cron production (tergantung daemon MCP).

## Procedure standar untuk scraping site CF-protected

1. **Tes endpoint langsung dulu** dengan `curl` + UA browser. Banyak site
   cuma proteksi halaman utama, bukan endpoint XHR. Kalau jalan → STOP, ga
   perlu Lightpanda.
2. Kalau curl 403/Cloudflare HTML challenge → baru pakai Lightpanda CDP
   mode dengan trick `about:blank` + `page.evaluate(fetch)`.
3. Untuk data yang murni di HTML utama (no XHR) → `lightpanda fetch --dump
   html` cukup.
4. **Jangan run cron-frequency tinggi** — site target bisa naikin proteksi.
   Tetap polite: min 5-15 menit interval, throttle, cache.

## Pitfalls

- `lightpanda fetch` **GET-only**. Kalau API target POST, harus pakai
  `serve` mode + `page.evaluate(fetch)`.
- **CDP: 1 connection per process.** Untuk paralel, start beberapa instance
  di port beda. Lightpanda start instant, jadi murah.
- **State reset on disconnect.** Tiap CDP connect harus `newContext` +
  `newPage`. Cookies & localStorage hilang saat ws close.
- `serve` daemon ga auto-restart. Bungkus pakai systemd / supervisor untuk
  production (lihat `references/install-on-server.md`).

## Verification

Setelah install:
```bash
lightpanda fetch --dump html https://example.com | grep -c "Example Domain"
# Output: 1 (kalau jalan)
```

Setelah CDP serve start:
```bash
curl -s http://127.0.0.1:9223/json/version | python3 -m json.tool | head
# Output: {"Browser": "Lightpanda/...", ...}
```

## Resep yang sudah terbukti

- `references/fetch-investing-calendar.md` — fetch economic calendar
  (CPI/FOMC/NFP) dari investing.com via Lightpanda CDP. Sudah dipakai untuk
  generate `hyperliquid/events.json`.
- `references/cloudflare-bypass.md` — pola umum lolos CF Turnstile.
- `references/install-on-server.md` — install di server (Linux/macOS),
  PATH setup, systemd, troubleshooting.
