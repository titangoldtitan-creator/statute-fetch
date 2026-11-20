#!/usr/bin/env python3
"""Second fetch method: render pages whose HTML came back as an empty script shell.

Usage: render.py <out_dir>   (out_dir holds _status.md and the fetched files)

A row is rendered only when the plain fetch returned HTTP 200, carries no bot-check
flag, and the page has less than MIN_TEXT characters of visible text. Pages with a
bot check are never rendered: we do not get around a site's protection. If the
rendered page itself shows a bot check, it is discarded and the row is marked.
The rendered copy is saved next to the original as <file>.rendered.html.
"""
import html
import os
import re
import sys

MIN_TEXT = 2000
CHECK = re.compile(r"cf-challenge|challenge-platform|Just a moment|Attention Required|"
                   r"Access Denied|I'm not a robot|verify you are human", re.I)


def visible_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|template)\b.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def safe(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", label)


def candidates(rows, out):
    for r in rows:
        if r["code"] != "200" or r["flag"].startswith("CHALLENGE"):
            continue
        p = os.path.join(out, safe(r["label"]))
        try:
            raw = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if "<html" not in raw[:5000].lower():
            continue  # PDF, JSON or plain text: nothing to render
        if len(visible_text(raw)) < MIN_TEXT:
            yield r, p


def read_status(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        c = [x.strip() for x in line.rstrip("\n").split("|")]
        if len(c) < 8 or c[1] in ("label", "") or c[1].startswith("---"):
            rows.append({"raw": line})
            continue
        # a page title may itself contain "|": everything between url and flag is title
        rows.append({"label": c[1], "code": c[2], "bytes": c[3], "url": c[4],
                     "title": " | ".join(c[5:-2]), "flag": c[-2]})
    return rows


def write_status(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            if "raw" in r:
                f.write(r["raw"])
            else:
                f.write(f"| {r['label']} | {r['code']} | {r['bytes']} | {r['url']} | {r['title']} | {r['flag']} |\n")


def main(out):
    status = os.path.join(out, "_status.md")
    rows = read_status(status)
    todo = list(candidates([r for r in rows if "raw" not in r], out))
    print(f"render candidates: {len(todo)}")
    if not todo:
        return
    from playwright.sync_api import sync_playwright
    exe = os.environ.get("CHROME_PATH") or None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=exe)
        page = browser.new_page()
        for r, p in todo:
            try:
                page.goto(r["url"], wait_until="networkidle", timeout=90000)
                page.wait_for_timeout(1500)
                rendered = page.content()
                text = page.inner_text("body")
            except Exception as e:  # noqa: BLE001 - report and move on
                r["flag"] = f"RENDER-ERR {type(e).__name__}"
                continue
            if CHECK.search(text) or CHECK.search(rendered[:20000]):
                r["flag"] = "RENDER-BOTCHECK"  # discarded, not worked around
                continue
            n = len(re.sub(r"\s+", " ", text).strip())
            if n < MIN_TEXT:
                r["flag"] = f"RENDER-THIN {n}"
                continue
            with open(p + ".rendered.html", "w", encoding="utf-8") as f:
                f.write(rendered)
            r["flag"] = f"RENDERED {n}"
        browser.close()
    write_status(status, rows)


if __name__ == "__main__":
    main(sys.argv[1])
