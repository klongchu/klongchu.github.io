# klongchu.github.io

Personal blog + GitHub Trending tracker, served with GitHub Pages.

## Pages
- `index.html` — home
- `blog.html` — blog posts
- `trending.html` — daily GitHub trending (reads `trending.json`)

## Auto-update
`.github/workflows/update-trending.yml` runs daily (00:30 UTC) via
`scripts/fetch_trending.py`, which scrapes github.com/trending using the
Python standard library and rewrites `trending.json`. You can also trigger
it manually from the Actions tab (workflow_dispatch).

## Local preview
```bash
python3 -m http.server 8000
# open http://localhost:8000
```
