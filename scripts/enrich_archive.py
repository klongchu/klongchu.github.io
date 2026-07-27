#!/usr/bin/env python3
"""Enrich archive.json repos that lack readme_thai_full with full Thai README translation."""
import json
import sys
import os
from pathlib import Path

# Add scripts dir to path so we can import fetch_trending
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_trending import fetch_readme, clean_markdown, summarize_readme_sections_th, translate_readme_paragraphs, readme_image_url

ARCHIVE = "archive.json"


def main():
    print("Loading archive.json...", flush=True)
    arc = json.loads(Path(ARCHIVE).read_text(encoding="utf-8"))
    repos = arc.get("repos", {})

    total = len(repos)
    need = {n: r for n, r in repos.items() if not r.get("readme_summary", {}).get("readme_thai_full")}
    print(f"Total: {total}, need enrichment: {len(need)}", flush=True)

    for i, (name, repo) in enumerate(need.items(), 1):
        print(f"[{i}/{len(need)}] {name}", flush=True)

        try:
            md = fetch_readme(name)
            if not md:
                print(f"  no README", flush=True)
                rs = repo.setdefault("readme_summary", {})
                rs["readme_thai_full"] = None
                continue

            # Update image from README if missing
            img = readme_image_url(name, md)
            if img:
                repo["image"] = img

            rs = repo.setdefault("readme_summary", {})

            # Clean markdown into lines for summary
            lines = clean_markdown(md)

            # Get formal Thai sections (uses Google Translate)
            formal_sections = summarize_readme_sections_th(md)
            if formal_sections:
                rs.update(formal_sections)

            # Get full README Thai translation
            thai_full = translate_readme_paragraphs(md)
            if thai_full:
                rs["readme_thai_full"] = thai_full

            # Update excerpt
            excerpt_lines = []
            for line in md.splitlines()[:80]:
                s = line.strip()
                if s and not s.startswith("!") and not s.startswith("<"):
                    excerpt_lines.append(s)
            rs["excerpt_raw"] = "\n".join(excerpt_lines[:40])

            print(f"  done — thai_full={len(thai_full or '')} chars", flush=True)
        except Exception as e:
            print(f"  ! FAILED: {e}", flush=True)
            continue

        # Save incremental
        if i % 10 == 0:
            Path(ARCHIVE).write_text(json.dumps(arc, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [checkpoint saved at {i}/{len(need)}]", flush=True)

    Path(ARCHIVE).write_text(json.dumps(arc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done. Enriched {len(need)} repos. Total archive: {len(repos)}", flush=True)


if __name__ == "__main__":
    main()
