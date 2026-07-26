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

THAI_EXPLANATIONS = {
    "permissionlesstech/bitchat": "แอปแชตแบบ Bluetooth mesh ใช้คุยกันได้แม้ไม่พึ่งอินเทอร์เน็ต แนวคิดคล้าย IRC สำหรับการสื่อสารระยะใกล้",
    "citrolabs/ego-lite": "เบราว์เซอร์สำหรับ AI agent ใช้ทำ web automation และแชร์สถานะล็อกอินของ browser ให้ agent ใช้งานต่อได้",
    "block/buzz": "แพลตฟอร์มสื่อสารแนว hive mind หรือระบบรวมความคิดและการประสานงานของหลายคน/หลาย agent",
    "pingdotgg/t3code": "โปรเจกต์สาย TypeScript จาก t3 ecosystem ใช้เป็นฐานหรือเครื่องมือช่วยพัฒนาแอปสมัยใหม่",
    "CoreBunch/Instatic": "CMS แบบ visual และ self-hosted แนว open-source แทน Webflow/Framer/WordPress โดยเน้น output เป็น static pages",
    "yorukot/superfile": "โปรแกรมจัดการไฟล์บน terminal หน้าตาทันสมัย ใช้งานสะดวก สำหรับคนทำงานใน CLI",
    "nodejs/node": "runtime สำหรับรัน JavaScript ฝั่ง server และเครื่องมือ command line เป็นแกนหลักของ ecosystem Node.js",
    "OtterMind/Chat2DB": "เครื่องมือจัดการฐานข้อมูลและ SQL client ที่มี AI ช่วยเขียน query สำรวจ schema และทำงานกับหลาย DB",
    "pbakaus/impeccable": "ชุดแนวคิดหรือ design language สำหรับช่วยให้ระบบ AI ทำงานด้าน design ได้ดีและสม่ำเสมอขึ้น",
    "shiyu-coder/Kronos": "foundation model สำหรับข้อมูลตลาดการเงิน ใช้วิเคราะห์ลำดับเหตุการณ์และรูปแบบใน financial markets",
    "alibaba/open-code-review": "เครื่องมือ code review แบบ hybrid ใช้ทั้งกฎเชิง deterministic และ LLM agent เพื่อช่วยตรวจ bug และช่องโหว่",
    "andrewyng/aisuite": "ไลบรารีรวม interface สำหรับเรียกใช้งานผู้ให้บริการ Generative AI หลายเจ้า ผ่าน API รูปแบบเดียว",
    "anthropics/claude-cookbooks": "ชุดตัวอย่าง notebook และ recipe สำหรับใช้งาน Claude ในงานจริง เช่น analysis, automation, และ prompting",
    "Pumpkin-MC/Pumpkin": "ซอฟต์แวร์ server สำหรับ Minecraft ที่เน้นความเร็วและประสิทธิภาพในการโฮสต์เกม",
    "permissionlesstech/bitchat-android": "เวอร์ชัน Android ของ bitchat ใช้แชตผ่าน Bluetooth mesh โดยไม่ต้องพึ่งเครือข่ายกลาง",
    "jenkinsci/jenkins": "automation server สำหรับ CI/CD ใช้ build, test, deploy และ orchestrate งานพัฒนาซอฟต์แวร์",
    "amnezia-vpn/amnezia-client": "ไคลเอนต์ VPN สำหรับเดสก์ท็อปและมือถือ ใช้เชื่อมต่อบริการ Amnezia VPN",
}

FALLBACK_THAI = {
    "bluetooth mesh chat": "ระบบแชตผ่าน Bluetooth mesh",
    "browser for ai agents": "เบราว์เซอร์สำหรับ AI agent",
    "communication platform": "แพลตฟอร์มสื่อสาร",
    "terminal file manager": "โปรแกรมจัดการไฟล์บน terminal",
    "database tool": "เครื่องมือจัดการฐานข้อมูล",
    "sql client": "โปรแกรมสำหรับใช้งาน SQL",
    "javascript runtime": "runtime สำหรับ JavaScript",
    "foundation model": "foundation model สำหรับงานเฉพาะทาง",
    "code review tool": "เครื่องมือช่วย code review",
    "interface to multiple generative ai providers": "เครื่องมือรวมทางเข้า API ของผู้ให้บริการ AI หลายเจ้า",
}


def thai_summary(name, description):
    if name in THAI_EXPLANATIONS:
        return THAI_EXPLANATIONS[name]
    desc = (description or "").strip()
    low = desc.lower()
    for key, value in FALLBACK_THAI.items():
        if key in low:
            return value
    return f"โปรเจกต์ภาษา {name.split('/')[0]}: {desc}" if desc else None


README_HINTS = {
    "install": ["install", "installation", "quick start", "getting started", "run without installing", "download"],
    "purpose": ["what is", "overview", "about", "why", "vision"],
    "usage": ["usage", "how to use", "quick start", "demo", "features"],
}


def fetch_readme(name):
    urls = [
        f"https://raw.githubusercontent.com/{name}/HEAD/README.md",
        f"https://raw.githubusercontent.com/{name}/HEAD/readme.md",
    ]
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            pass
    return None


def readme_image_url(name, md):
    if not md:
        return None
    candidates = []
    candidates += re.findall(r'!\[[^\]]*\]\(([^)\s]+)', md)
    candidates += re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', md, re.I)
    if not candidates:
        return None

    def normalize(src):
        src = src.strip()
        if src.startswith('http://') or src.startswith('https://'):
            return src
        if src.startswith('./'):
            src = src[2:]
        if src.startswith('/'):
            src = src[1:]
        return f"https://raw.githubusercontent.com/{name}/HEAD/{src}"

    def score(src):
        low = src.lower()
        bad = ['img.shields.io', 'badge', 'logo', 'icon', 'emoji', 'avatar', '.svg']
        if any(b in low for b in bad):
            return -10
        good = ['screenshot', 'banner', 'demo', 'cover', 'preview', 'hero', 'assets/', 'docs/']
        s = 0
        for g in good:
            if g in low:
                s += 3
        if any(low.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']):
            s += 2
        if 'user-attachments/assets' in low:
            s += 4
        return s

    ranked = sorted((normalize(c) for c in candidates), key=score, reverse=True)
    best = ranked[0]
    return best if score(best) > 0 else None


def clean_markdown(md):
    lines = []
    for line in md.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith('![') or s.startswith('<img') or s.startswith('<div') or s.startswith('</div'):
            continue
        if s.startswith('```'):
            continue
        s = re.sub(r'`([^`]+)`', r'\1', s)
        s = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', s)
        s = re.sub(r'<[^>]+>', '', s)
        s = re.sub(r'^#+\s*', '', s)
        s = re.sub(r'^[-*]\s*', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        if s:
            lines.append(s)
    return lines


def first_matching_block(lines, keywords, default=6):
    for i, line in enumerate(lines):
        low = line.lower()
        if any(k in low for k in keywords):
            block = []
            for j in range(i + 1, min(i + 8, len(lines))):
                if len(lines[j]) < 2:
                    break
                block.append(lines[j])
                if len(' '.join(block)) > 300:
                    break
            if block:
                return ' '.join(block)
    return ' '.join(lines[:default])


def summarize_readme_th(name, description):
    md = fetch_readme(name)
    if not md:
        return None, None, None
    lines = clean_markdown(md)
    if not lines:
        return None, None, None

    what = first_matching_block(lines, README_HINTS['purpose'])
    usage = first_matching_block(lines, README_HINTS['usage'])
    purpose = first_matching_block(lines, README_HINTS['install'])

    summary = {
        'what_is_it': thai_summary(name, description) or what,
        'how_to_use': usage,
        'purpose': what,
    }
    return summary, '\\n'.join(lines[:80]), readme_image_url(name, md)


class TrendingParser(HTMLParser):
    """Extract repo rows from the trending page markup."""

    def __init__(self):
        super().__init__()
        self.repos = []
        self._in_article = False
        self._in_h2 = False
        self._in_desc = False
        self._in_lang = False
        self._capture_href = None
        self._cur = None
        self._text_buf = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class") or ""
        if tag == "article" and "Box-row" in cls:
            self._in_article = True
            self._cur = {"name": None, "url": None, "description": None,
                         "language": None, "stars": 0, "forks": 0, "stars_today": None}
        elif self._in_article and tag == "h2":
            self._in_h2 = True
        elif self._in_article and self._in_h2 and tag == "a" and self._cur is not None:
            href = d.get("href") or ""
            self._cur["url"] = "https://github.com" + href
            self._cur["name"] = href.strip("/")
        elif self._in_article and tag == "p" and "col-9" in cls:
            self._in_desc = True
            self._text_buf = []
        elif self._in_article and tag == "span" and d.get("itemprop") == "programmingLanguage":
            self._in_lang = True
            self._text_buf = []

    def handle_endtag(self, tag):
        if tag == "h2" and self._in_h2:
            self._in_h2 = False
        elif tag == "p" and self._in_desc and self._cur is not None:
            self._in_desc = False
            desc = " ".join("".join(self._text_buf).split())
            self._cur["description"] = desc or None
        elif tag == "span" and self._in_lang and self._cur is not None:
            self._in_lang = False
            self._cur["language"] = "".join(self._text_buf).strip() or None
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
        if self._in_desc or self._in_lang:
            self._text_buf.append(data)


def parse_int(text):
    return int(re.sub(r"[^\d]", "", text) or 0)


def _extract_count_after_link(html, name, kind):
    m = re.search(rf'href="/{re.escape(name)}/{kind}"[^>]*>(.*?)</a>', html, re.S)
    if not m:
        return 0
    text = re.sub(r'<[^>]+>', ' ', m.group(1))
    return parse_int(text)


def enrich_stats(html, repos):
    """Pull star/fork counts and 'stars today' via regex over full page."""
    todays = [parse_int(m.group(1)) for m in re.finditer(r'([\d,]+)\s+stars today', html)]

    for repo in repos:
        name = repo["name"]
        repo["stars"] = _extract_count_after_link(html, name, 'stargazers')
        repo["forks"] = _extract_count_after_link(html, name, 'forks')

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
    # reorder keys and add image
    ordered = []
    for r in repos:
        readme_summary, readme_excerpt, readme_image = summarize_readme_th(r["name"], r["description"])
        ordered.append({
            "rank": r["rank"], "name": r["name"], "description": r["description"],
            "thai_description": thai_summary(r["name"], r["description"]),
            "language": r["language"], "stars": r["stars"], "forks": r["forks"],
            "stars_today": r["stars_today"], "url": r["url"],
            "image": readme_image or f"https://opengraph.githubassets.com/1/{r['name']}",
            "readme_summary": readme_summary,
            "readme_excerpt": readme_excerpt,
        })

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
