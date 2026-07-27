#!/usr/bin/env python3
"""Backfill archive.json with top 100 recently-created repos via GitHub Search API.

Merges with existing archive.json (dedupe by name). Uses same enrichment as fetch_trending.py:
Thai description, README image, README Thai translation.
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# reuse enrichment from fetch_trending
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_trending import (
    fetch_readme, summarize_readme_th, thai_summary, readme_image_url
)

ARCHIVE = "archive.json"
SEARCH_URL = "https://api.github.com/search/repositories?q=created:>2026-06-01+stars:>100&sort=stars&order=desc&per_page=100"


def search_recent_top():
    req = urllib.request.Request(SEARCH_URL, headers={"User-Agent": "klongchu-trending", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("items", [])


def enrich(item):
    name = item["full_name"]
    desc = item.get("description")
    print(f"  processing {name}", flush=True)
    readme_summary, readme_excerpt, readme_image, readme_md = summarize_readme_th(name, desc)
    return {
        "name": name,
        "description": desc,
        "thai_description": thai_summary(name, desc, readme_md),
        "language": item.get("language"),
        "stars": item.get("stargazers_count", 0),
        "forks": item.get("forks_count", 0),
        "stars_today": None,
        "url": item.get("html_url"),
        "image": readme_image or f"https://opengraph.githubassets.com/1/{name}",
        "readme_summary": readme_summary,
        "readme_excerpt": readme_excerpt,
        "created_at": item.get("created_at"),
        "source": "github-search-backfill",
    }


def load_archive():
    if not os.path.exists(ARCHIVE):
        return {"repos": {}, "updated_at": None}
    try:
        with open(ARCHIVE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"repos": {}, "updated_at": None}


def save_archive(data):
    with open(ARCHIVE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("Fetching top 100 recently-created repos from GitHub Search API...", flush=True)
    items = search_recent_top()
    print(f"Got {len(items)} repos, enriching...", flush=True)

    archive = load_archive()
    archive.setdefault("repos", {})

    for i, item in enumerate(items, 1):
        name = item["full_name"]
        print(f"[{i}/{len(items)}] {name}", flush=True)
        try:
            archive["repos"][name] = enrich(item)
        except Exception as e:
            print(f"  ! failed {name}: {e}", flush=True)
            continue

    archive["updated_at"] = datetime.now(timezone.utc).isoformat()
    archive["total_count"] = len(archive["repos"])
    save_archive(archive)
    print(f"Saved {archive['total_count']} repos to {ARCHIVE}", flush=True)


if __name__ == "__main__":
    main()
