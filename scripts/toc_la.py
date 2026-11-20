#!/usr/bin/env python3
"""Louisiana table of contents -> fetch list.

legis.la.gov opens each title of a code through an ASP.NET postback, so the section
links are not in the HTML of the contents page. This script sends the same form
post the browser sends when a title is clicked and collects the Law.aspx?d=<id>
links. Output: one "LA_<folder>_<id> <url>" line per document, ready for lists/.

Usage: toc_la.py <folder> [<folder> ...]   (75 = Revised Statutes, 72 = Constitution)
"""
import re
import sys
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
BASE = "https://legis.la.gov/legis/"


def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    if data is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", "ignore")


def hidden_fields(html):
    return dict(re.findall(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', html))


def law_ids(html):
    return re.findall(r'Law\.aspx\?d=(\d+)', html)


def harvest(folder):
    url = f"{BASE}Laws_Toc.aspx?folder={folder}&level=Parent"
    page = get(url)
    form = hidden_fields(page)
    targets = re.findall(r"__doPostBack\(&#39;([^&]+LinkButton1a)&#39;", page)
    seen, rows = set(), []
    for i in law_ids(page):  # some contents pages list documents directly
        if i not in seen:
            seen.add(i)
            rows.append(i)
    for t in targets:
        body = dict(form, __EVENTTARGET=t, __EVENTARGUMENT="")
        html = get(url, urllib.parse.urlencode(body).encode())
        for i in law_ids(html):
            if i not in seen:
                seen.add(i)
                rows.append(i)
        time.sleep(0.7)
    print(f"folder {folder}: {len(targets)} titles, {len(rows)} documents", file=sys.stderr)
    return [f"LA_{folder}_{i} {BASE}Law.aspx?d={i}" for i in rows]


if __name__ == "__main__":
    for f in sys.argv[1:]:
        for line in harvest(f):
            print(line)
