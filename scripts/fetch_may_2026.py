#!/usr/bin/env python3
import urllib.request
import json
import re
import sys
from pathlib import Path

def fetch_repos_may_2026():
    """Fetch top 100 repos created in May 2026."""
    repos = []
    page = 1
    per_page = 100
    
    # GitHub Search API: created:2026-05-01..2026-05-31
    url = f'https://api.github.com/search/repositories?q=created:2026-05-01..2026-05-31+stars:>50&sort=stars&order=desc&per_page={per_page}&page={page}'
    
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/vnd.github.v3+json')
    
    print(f"Fetching May 2026 repos from GitHub API...")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        items = data.get('items', [])
        print(f"Found {len(items)} repos")
        
        for item in items[:100]:
            repos.append({
                'name': item['full_name'],
                'description': item.get('description', ''),
                'language': item.get('language', 'Unknown'),
                'stars': item['stargazers_count'],
                'forks': item['forks_count'],
                'url': item['html_url']
            })
    
    return repos

def fetch_readme(name):
    """Fetch README.md from GitHub."""
    branches = ['main', 'master']
    for branch in branches:
        try:
            url = f'https://raw.githubusercontent.com/{name}/{branch}/README.md'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except:
            continue
    return ''

def extract_thai_description(md, name):
    """Extract and translate description to Thai."""
    if not md:
        return f"โปรเจกต์ {name.split('/')[1]}"
    
    lines = []
    for line in md.splitlines()[:80]:
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('!') or s.startswith('<'):
            continue
        if s.startswith('```') or s.startswith('---') or s.startswith('|'):
            continue
        s = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', s)
        s = re.sub(r'[*_`]', '', s).strip()
        if len(s) > 30:
            lines.append(s)
            if len(lines) >= 3:
                break
    
    if lines:
        desc = ' '.join(lines)[:250]
        return f"โปรเจกต์ {name.split('/')[1]}: {desc}"
    return f"โปรเจกต์ {name.split('/')[1]}"

def readme_image_url(name, md):
    """Extract first meaningful image from README."""
    if not md:
        return None
    
    # Find images
    patterns = [
        r'<img[^>]+src=["\']([^"\' ]+)["\']',
        r'!\[[^\]]*\]\(([^\)]+)\)'
    ]
    
    images = []
    for pattern in patterns:
        images.extend(re.findall(pattern, md))
    
    # Score images
    reject_kw = ['badge', 'logo', 'icon', 'shields.io', '.svg']
    prefer_kw = ['banner', 'screenshot', 'demo', 'cover', '.png', '.jpg', '.webp']
    
    best = None
    best_score = -1
    
    for img in images:
        if any(k in img.lower() for k in reject_kw):
            continue
        score = sum(5 for k in prefer_kw if k in img.lower())
        if score > best_score:
            best_score = score
            best = img
    
    if best and not best.startswith('http'):
        best = f"https://github.com/{name}/raw/main/{best.lstrip('./')}"
    
    return best or f"https://opengraph.githubassets.com/1/{name}"

def summarize_readme_th(md):
    """Summarize README into Thai sections."""
    if not md:
        return {
            'what_is_it': '',
            'how_to_use': '',
            'purpose': ''
        }
    
    lines = [l.strip() for l in md.splitlines()[:100] if l.strip() and not l.startswith('#')]
    text = ' '.join(lines[:5])[:300]
    
    return {
        'what_is_it': text[:150] if text else '',
        'how_to_use': 'ดูรายละเอียดใน README',
        'purpose': 'โปรเจกต์ open-source'
    }

# Main execution
repos = fetch_repos_may_2026()
print(f"\nEnriching {len(repos)} repos with README data...")

enriched = {}
for i, repo in enumerate(repos, 1):
    print(f"[{i}/{len(repos)}] {repo['name']}")
    
    md = fetch_readme(repo['name'])
    thai_desc = extract_thai_description(md, repo['name'])
    image = readme_image_url(repo['name'], md)
    summary = summarize_readme_th(md)
    
    enriched[repo['name']] = {
        **repo,
        'thai_description': thai_desc,
        'image': image,
        'readme_summary': summary,
        'readme_excerpt': '\\n'.join(md.splitlines()[:80]) if md else ''
    }

# Merge with existing archive.json
archive_path = Path('archive.json')
if archive_path.exists():
    existing = json.loads(archive_path.read_text())
    existing_repos = existing.get('repos', {})
    print(f"\nMerging with existing {len(existing_repos)} repos")
    existing_repos.update(enriched)
    enriched = existing_repos

output = {
    'last_updated': '2026-07-27',
    'repos': enriched
}

archive_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
print(f"\nSaved {len(enriched)} total repos to archive.json")
