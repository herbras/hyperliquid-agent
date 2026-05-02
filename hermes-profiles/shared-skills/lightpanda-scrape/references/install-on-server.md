# Install Lightpanda di Server

Panduan install Lightpanda untuk dipakai agent (Hermes scout, sniper, journal,
atau cron scraper apapun). OS support: **Linux x86_64**, **Linux arm64**,
**macOS arm64 (Apple Silicon)**, **macOS x86_64**. Windows: pakai WSL2.

## Quick install (recommended)

```bash
curl -fsSL https://pkg.lightpanda.io/install.sh | bash
```

Script akan:
1. Detect OS + arch.
2. Download binary nightly terbaru dari `pkg.lightpanda.io`.
3. Place ke `$HOME/.local/bin/lightpanda` + `chmod +x`.

Setelah install, tambah ke PATH (kalau belum):

```bash
# bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc

# fish
fish_add_path $HOME/.local/bin

# zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

Verify:

```bash
which lightpanda
lightpanda --help | head -3
```

## Update

Lightpanda binary nightly evolve cepat — kalau crash atau behavior aneh,
re-run install script (max 1x per hari):

```bash
curl -fsSL https://pkg.lightpanda.io/install.sh | bash
```

## Install dependencies untuk CDP mode

CDP mode butuh Node.js + `playwright-core` (atau `puppeteer-core`):

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y nodejs npm

# macOS (Homebrew)
brew install node

# Project-local install playwright-core (no browser binary needed —
# Lightpanda IS the browser)
mkdir -p ~/scraper && cd ~/scraper
npm init -y
npm install playwright-core
```

Catatan: pakai **`playwright-core`** atau **`puppeteer-core`**, bukan full
package. Versi `core` ga download Chromium binary (yang ga kita pakai).

## Setup MCP server (opsional, untuk Claude Code agent)

```bash
# Claude Code (CLI tool — bukan API)
claude mcp add lightpanda -- $HOME/.local/bin/lightpanda mcp
```

Verify di sesi Claude Code:
```
/mcp list
# Harus terlihat: lightpanda — connected
```

## Setup CDP server sebagai daemon (production)

### systemd (Linux)

`/etc/systemd/system/lightpanda-cdp.service`:

```ini
[Unit]
Description=Lightpanda CDP Server
After=network.target

[Service]
Type=simple
User=ubuntu
ExecStart=/home/ubuntu/.local/bin/lightpanda serve --host 127.0.0.1 --port 9223
Restart=on-failure
RestartSec=5

# Tighten — Lightpanda ga butuh akses luas
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable + start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lightpanda-cdp
sudo systemctl status lightpanda-cdp
```

Cek port aktif:

```bash
curl -s http://127.0.0.1:9223/json/version
```

### launchd (macOS)

`~/Library/LaunchAgents/io.lightpanda.cdp.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>            <string>io.lightpanda.cdp</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/USERNAME/.local/bin/lightpanda</string>
    <string>serve</string>
    <string>--host</string><string>127.0.0.1</string>
    <string>--port</string><string>9223</string>
  </array>
  <key>RunAtLoad</key>        <true/>
  <key>KeepAlive</key>        <true/>
  <key>StandardOutPath</key>  <string>/tmp/lightpanda.log</string>
  <key>StandardErrorPath</key><string>/tmp/lightpanda.err</string>
</dict>
</plist>
```

Load:

```bash
launchctl load ~/Library/LaunchAgents/io.lightpanda.cdp.plist
```

## Troubleshooting

### "command not found"
PATH belum terupdate. Run `source ~/.bashrc` (atau buka shell baru), atau
panggil pakai full path: `$HOME/.local/bin/lightpanda`.

### `--version` print error / log fatal
Versi nightly tertentu ga support flag `--version`. Tes pakai `--help` saja:
```bash
lightpanda --help | head -1
```

### `script fetch error err=Abort` di log
Normal. Lightpanda block beberapa script pihak ketiga (analytics, ads).
Bukan error fatal — fetch tetap berhasil.

### CDP connect timeout / EADDRINUSE
Port 9223 dipakai. Cek dulu:
```bash
lsof -nP -iTCP:9223 -sTCP:LISTEN
# kill proses, atau pakai port lain (--port 9224)
```

### `Execution context was destroyed`
Page navigate ulang saat lagi `evaluate`. Solusi: pakai `await
page.waitForLoadState('networkidle')` atau langsung `goto('about:blank')`
kalau cuma butuh JS context untuk panggil endpoint XHR (lihat
`cloudflare-bypass.md`).

### Crash / hang berulang
Update binary (`curl ... | bash`) dan retry. Kalau persist, report ke
https://github.com/lightpanda-io/browser/issues — sertakan trace + script
reproduksi.

## Disk + memory footprint

- Binary: ~10-20 MB
- Runtime memory: ~50-150 MB per CDP context (vs Chromium ~500MB+)
- Start time: <100ms (vs Chromium ~1-3s)

Aman buat run di VPS kecil (1GB RAM cukup untuk 3-5 paralel context).
