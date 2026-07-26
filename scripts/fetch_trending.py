#!/usr/bin/env python3
"""Fetch GitHub trending repositories and write trending.json.

GitHub has no official trending API, so we scrape the public
https://github.com/trending page with the standard library only
(no third-party deps needed in CI).
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

TRENDING_URL = "https://github.com/trending"
OUTPUT = "trending.json"


class TrendingParser(HTMLParser):
    """Extract repo rows from the trending page markup."""

    def __init__(self):
        super().__init__()
        self.repos = []
        self._in_article = False
        self._in_h2 = False
        self._in_desc = False
        self._capture_href = None
        self._cur = None
        self._text_buf = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class") or ""
        if tag == "article" and "Box-row" in cls:
            self._in_article = True
            self._cur = {"name": None, "url": None, "description": None,
                         "stars": 0, "forks": 0, "stars_today": None}
        elif self._in_article and tag == "h2":
            self._in_h2 = True
        elif self._in_article and self._in_h2 and tag == "a" and self._cur is not None:
            href = d.get("href") or ""
            self._cur["url"] = "https://github.com" + href
            self._cur["name"] = href.strip("/")
        elif self._in_article and tag == "p" and "col-9" in cls:
            self._in_desc = True
            self._text_buf = []

    def handle_endtag(self, tag):
        if tag == "h2" and self._in_h2:
            self._in_h2 = False
        elif tag == "p" and self._in_desc and self._cur is not None:
            self._in_desc = False
            desc = " ".join("".join(self._text_buf).split())
            self._cur["description"] = desc or None
        elif tag == "article" and self._in_article:
            self._in_article = False
            if self._cur and self._cur.get("name"):
                self.repos.append(self._cur)
            self._cur = None

    def handle_data(self, data):
        if self._in_h2 and self._cur is not None:
            # repo name text like "owner /\n repo"
            txt = "".join(data.split())
            if txt and self._cur["name"] is None:
                self._cur["name"] = txt
        if self._in_desc:
            self._text_buf.append(data)


def parse_int(text):
    return int(re.sub(r"[^\d]", "", text) or 0)


def enrich_stats(html, repos):
    """Pull star/fork counts and 'stars today' via regex over the full page."""
    # stars today: e.g. "1,198 stars today"
    today_map = {}
    for m in re.finditer(r'([\d,]+)\s+stars today', html):
        today_map.setdefault(m.start(), parse_int(m.group(1)))
    todays = [parse_int(m.group(1)) for m in re.finditer(r'([\d,]+)\s+stars today', html)]

    # star & fork counts follow /owner/repo/stargazers and /forks hrefs
    for repo in repos:
        name = repo["name"]
        s = re.search(rf'href="/{re.escape(name)}/stargazers"[^>]*>\s*([\d,]+)', html)
        f = re.search(rf'href="/{re.escape(name)}/forks"[^>]*>\s*([\d,]+)', html)
        if s:
            repo["stars"] = parse_int(s.group(1))
        if f:
            repo["forks"] = parse_int(f.group(1))
    for i, repo in enumerate(repos):
        if i < len(todays):
            repo["stars_today"] = todays[i]


def main():
    req = urllib.request.Request(TRENDING_URL, headers={"User-Agent": "Mozilla/5.0 (trending-bot)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    parser = TrendingParser()
    parser.feed(html)
    repos = parser.repos

    if not repos:
        print("ERROR: no repos parsed — page structure may have changed", file=sys.stderr)
        sys.exit(1)

    enrich_stats(html, repos)

    for i, repo in enumerate(repos, 1):
        repo["rank"] = i
    # reorder keys
    ordered = [{
        "rank": r["rank"], "name": r["name"], "description": r["description"],
        "stars": r["stars"], "forks": r["forks"], "stars_today": r["stars_today"],
        "url": r["url"],
    } for r in repos]

    out = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "trending_repos": ordered,
        "total_count": len(ordered),
    }
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {len(ordered)} repos to {OUTPUT}")


if __name__ == "__main__":
    main()
