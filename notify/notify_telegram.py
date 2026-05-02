#!/usr/bin/env python3
"""
notify_telegram.py — kirim message ke Telegram chat.

Pakai:
  echo "scan result" | python3 notify_telegram.py
  python3 notify_telegram.py "BTC GO-LONG 67420"
  python3 notify_telegram.py --file scan-output.txt

Env yang dipakai:
  TELEGRAM_BOT_TOKEN   wajib (dari @BotFather)
  TELEGRAM_CHAT_ID     wajib (chat id atau channel @username)
  TELEGRAM_PARSE_MODE  optional, default "MarkdownV2"; set "" untuk plain text
  TELEGRAM_DISABLE_PREVIEW  optional, "1" untuk matikan link preview
"""
import os
import sys
import json
import urllib.request
import urllib.parse
import argparse


MAX_LEN = 4000  # batas Telegram 4096; sisain margin untuk wrap


def md_escape(text: str) -> str:
    """Escape karakter khusus MarkdownV2 — di luar code block saja."""
    chars = r"_*[]()~`>#+-=|{}.!"
    out = []
    in_code = False
    i = 0
    while i < len(text):
        # detect ``` block
        if text[i:i+3] == "```":
            in_code = not in_code
            out.append("```")
            i += 3
            continue
        # detect `inline` code
        if text[i] == "`" and not in_code:
            out.append("`")
            i += 1
            j = text.find("`", i)
            if j == -1:
                continue
            out.append(text[i:j])
            out.append("`")
            i = j + 1
            continue
        c = text[i]
        if in_code:
            out.append(c)
        elif c in chars:
            out.append("\\" + c)
        else:
            out.append(c)
        i += 1
    return "".join(out)


def chunk(text: str, n: int = MAX_LEN):
    while text:
        # potong di newline terdekat <= n
        if len(text) <= n:
            yield text
            return
        cut = text.rfind("\n", 0, n)
        if cut == -1:
            cut = n
        yield text[:cut]
        text = text[cut:].lstrip("\n")


def send(token: str, chat_id: str, text: str, parse_mode: str, no_preview: bool):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": no_preview,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("message", nargs="?", help="message text; jika kosong, baca stdin")
    ap.add_argument("--file", help="baca message dari file")
    ap.add_argument("--prefix", default="", help="prepend ke setiap chunk")
    ap.add_argument("--plain", action="store_true", help="paksa parse_mode kosong")
    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID wajib di-set.",
              file=sys.stderr)
        sys.exit(2)

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    elif args.message:
        text = args.message
    else:
        text = sys.stdin.read()

    text = text.strip()
    if not text:
        print("ERROR: empty message", file=sys.stderr)
        sys.exit(2)

    parse_mode = "" if args.plain else os.environ.get("TELEGRAM_PARSE_MODE", "MarkdownV2")
    no_preview = os.environ.get("TELEGRAM_DISABLE_PREVIEW", "1") == "1"

    sent = 0
    for piece in chunk(text):
        body = (args.prefix + piece) if args.prefix else piece
        if parse_mode == "MarkdownV2":
            body = md_escape(body)
        status, resp = send(token, chat_id, body, parse_mode, no_preview)
        if status != 200:
            print(f"ERROR {status}: {resp}", file=sys.stderr)
            sys.exit(1)
        sent += 1

    print(f"OK sent {sent} message(s)")


if __name__ == "__main__":
    main()
