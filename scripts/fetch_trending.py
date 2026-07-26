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
    "permissionlesstech/bitchat": "แอปแชตแบบ peer-to-peer ที่ใช้ Bluetooth mesh network และ Nostr protocol ทำงานได้แม้ไม่มีอินเทอร์เน็ต ไม่ต้องสมัครบัญชี ไม่มี server กลาง เหมาะกับการสื่อสารแบบกระจายศูนย์หรือสถานการณ์ที่เครือข่ายปกติใช้ไม่ได้",
    "citrolabs/ego-lite": "เบราว์เซอร์ที่ออกแบบมาให้คนและ AI agents ใช้งานร่วมกันได้โดยตรง ใช้ทำ web automation, แชร์สถานะ login/session, และให้ agent รันงานใน Space แยกโดยไม่รบกวนแท็บหลักของผู้ใช้",
    "block/buzz": "workspace สำหรับทีมที่มนุษย์และ AI agents ทำงานร่วมกันบน relay ที่คุณดูแลเองได้ ใช้ event log เดียวเก็บทั้งข้อความ workflow review และ git activity เพื่อให้การทำงานร่วมกันตรวจสอบย้อนหลังได้",
    "pingdotgg/t3code": "web GUI สำหรับ coding agents หลายเจ้า เช่น Codex, Claude, Cursor และ OpenCode ช่วยรวมการใช้งาน AI coding assistant ไว้ในหน้าเดียว เหมาะกับคนที่อยากได้ interface กลางที่เรียบง่ายและใช้งานเร็ว",
    "CoreBunch/Instatic": "CMS แบบ visual editor ที่ self-hosted ได้ ทำงานรวม editor, content engine, media, forms, auth และ publisher ไว้ใน Bun server เดียว จุดเด่นคือ export ออกมาเป็น semantic HTML และ CSS ที่เบาและอ่านง่าย",
    "yorukot/superfile": "โปรแกรมจัดการไฟล์สำหรับ terminal ที่เน้นประสบการณ์ใช้งานสมัยใหม่ มีหน้าตาใช้ง่าย รองรับการ preview ไฟล์ การนำทางด้วยคีย์บอร์ด และงานจัดการไฟล์ทั่วไป เหมาะกับคนที่ทำงานใน CLI เป็นหลัก",
    "nodejs/node": "JavaScript runtime แบบข้ามแพลตฟอร์มสำหรับรันโค้ดฝั่ง server และ command line ใช้ V8 engine เป็นแกนหลัก และเป็นรากฐานสำคัญของ ecosystem Node.js สำหรับ backend, tooling และ automation",
    "OtterMind/Chat2DB": "เครื่องมือจัดการฐานข้อมูลและ SQL workspace ที่มี AI assistant ช่วยเขียน อธิบาย และปรับปรุง SQL รองรับฐานข้อมูลจำนวนมาก พร้อมความสามารถดู schema, แก้ข้อมูล, import/export และทำงานวิเคราะห์ข้อมูลได้ในตัว",
    "pbakaus/impeccable": "ชุดแนวคิดและแนวทางออกแบบสำหรับงานที่ให้ AI ช่วยสร้างงานดีไซน์หรือ UI เน้นทำให้ผลลัพธ์มีความสม่ำเสมอ สื่อสารกับโมเดลง่ายขึ้น และวางระบบการออกแบบให้ทีมใช้งานต่อได้จริง",
    "shiyu-coder/Kronos": "foundation model สำหรับข้อมูลตลาดการเงิน ออกแบบมาเพื่อวิเคราะห์ time series และรูปแบบใน financial markets ช่วยงานคาดการณ์แนวโน้มและทำความเข้าใจพฤติกรรมของข้อมูลการเงิน",
    "alibaba/open-code-review": "เครื่องมือ code review แบบ hybrid ที่ใช้ทั้ง deterministic rules และ LLM agent ร่วมกัน เพื่อตรวจจับ bug, issue ด้าน thread safety, XSS, SQL injection และปัญหาคุณภาพโค้ดแบบ line-level",
    "andrewyng/aisuite": "ไลบรารีที่รวม interface สำหรับเรียกใช้งานผู้ให้บริการ Generative AI หลายเจ้าไว้ในรูปแบบเดียว ช่วยลดความยุ่งยากเวลาเปลี่ยน model provider หรือเขียนแอปที่ต้องรองรับหลาย backend",
    "anthropics/claude-cookbooks": "ชุดตัวอย่าง notebook และ recipe สำหรับใช้งาน Claude ในงานจริง เช่น data analysis, workflow automation, prompting และการประยุกต์ใช้โมเดลกับ use case ต่าง ๆ",
    "Pumpkin-MC/Pumpkin": "Minecraft server implementation ที่เน้นประสิทธิภาพและความเร็วในการโฮสต์เกม ช่วยลดการใช้ทรัพยากรและเหมาะกับคนที่ต้องการ server ทางเลือกที่ optimize มากขึ้น",
    "permissionlesstech/bitchat-android": "เวอร์ชัน Android ของ bitchat สำหรับแชตผ่าน Bluetooth mesh แบบไม่พึ่งโครงสร้างเครือข่ายกลาง เหมาะกับการสื่อสารออฟไลน์หรือในพื้นที่ที่อินเทอร์เน็ตไม่เสถียร",
    "jenkinsci/jenkins": "automation server สำหรับงาน CI/CD ใช้ build, test, deploy และ orchestrate pipeline ต่าง ๆ ในกระบวนการพัฒนาซอฟต์แวร์ รองรับ plugin จำนวนมากและปรับแต่ง workflow ได้สูง",
    "amnezia-vpn/amnezia-client": "ไคลเอนต์ VPN สำหรับเดสก์ท็อปและมือถือ ใช้เชื่อมต่อบริการ Amnezia VPN เพื่อช่วยให้ผู้ใช้ตั้งค่าและใช้งานการเชื่อมต่อที่เน้นความเป็นส่วนตัวได้สะดวกขึ้น",
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


def extract_thai_description_from_readme(md):
    """Extract description from README and translate to detailed Thai."""
    if not md:
        return None
    
    lines = []
    in_features = False
    feature_lines = []
    
    for i, line in enumerate(md.splitlines()[:150]):
        s = line.strip()
        
        # Track features section
        if re.match(r'^#+\s*(features|what|highlights|key features)', s, re.I):
            in_features = True
            continue
        elif in_features and s.startswith('#'):
            in_features = False
        
        if in_features and (s.startswith('-') or s.startswith('*') or s.startswith('•')):
            clean = re.sub(r'^[-*•]\s*\*\*?', '', s)
            clean = re.sub(r'\*\*?:?\s*', '', clean)
            clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean)
            clean = re.sub(r'`([^`]+)`', r'\1', clean)
            if len(clean) > 10:
                feature_lines.append(clean)
        
        if not s or s.startswith('#'):
            continue
        if s.startswith('![') or s.startswith('<img') or s.startswith('<div'):
            continue
        if s.startswith('```') or s.startswith('---') or s.startswith('|'):
            continue
        if s.startswith('[') or s.startswith('[![') or s.startswith('<a'):
            continue
        s = re.sub(r'<[^>]+>', '', s)
        s = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', s)
        s = re.sub(r'[*_`]', '', s)
        s = s.strip()
        # Skip command/code/URL lines
        if re.search(r'(curl |bash |wget |npm |npx |pip |brew |apt |sudo |powershell|Invoke-|https?://\S+\.(sh|ps1)|winget |cargo |go install)', s, re.I):
            continue
        if s.count('/') > 3 or s.startswith('$') or s.startswith('>'):
            continue
        if len(s) > 30:
            lines.append(s)
            if len(lines) >= 8:
                break
    
    if not lines:
        return None
    
    full = ' '.join(lines)
    low = full.lower()
    features = ' '.join(feature_lines[:5])
    
    # Detailed pattern matching with features
    if ('browser for ai' in low or 'browser for agent' in low or ('browser' in low and 'web automation' in low)):
        base = 'เบราว์เซอร์ที่ออกแบบมาให้ทำงานร่วมกับ AI agents โดยคนกับ agent สามารถใช้ browser ตัวเดียวกันได้พร้อมกัน agent รัน automation ใน Space แยก ไม่รบกวนแท็บของคุณ'
        if 'login' in low:
            base += ' และแชร์สถานะ login/session ระหว่างกันได้ ไม่ต้อง setup browser แยก'
        if features:
            base += f' ความสามารถ: {features[:200]}'
        return base
    
    elif 'mesh' in low and 'bluetooth' in low and 'chat' in low:
        base = 'แอพแชทแบบ peer-to-peer ที่ใช้ Bluetooth mesh network และ Nostr protocol ทำงานได้แม้ไม่มีอินเทอร์เน็ต ไม่ต้องสมัครบัญชี ไม่มี server กลาง'
        if 'nostr' in low:
            base += ' มี dual transport คือใช้ Bluetooth สำหรับ offline และ Nostr สำหรับ internet-based messaging'
        if 'encryption' in low:
            base += ' มี end-to-end encryption ด้วย Noise Protocol'
        return base
    
    elif 'workspace' in low and ('relay' in low or 'nostr' in low or 'humans and ai' in low):
        base = 'workspace สำหรับทีมที่มนุษย์และ AI agents ทำงานร่วมกัน ใช้ Nostr relay เป็นฐาน ทุกอย่างเป็น signed events ใน log เดียว ไม่ว่าจะเป็นข้อความ reaction workflow git event'
        if 'self-host' in low:
            base += ' self-host ได้ รัน relay เองบน infrastructure ของคุณ'
        if features:
            base += f' agents สามารถ: {features[:180]}'
        return base
    
    elif 'cms' in low and ('visual' in low or 'self-host' in low):
        base = 'CMS แบบ visual editor ที่ทำงานบน Bun server เดียว รวมทั้ง editor, content engine, media, auth, forms, plugins และ publisher'
        if 'static' in low or 'html' in low:
            base += ' output เป็น plain semantic HTML และ compact CSS ไม่มี framework runtime เหลือค้าง โหลดเร็วเหมือน static file'
        if 'self-host' in low:
            base += ' self-hosted ใช้ SQLite หรือ Postgres'
        return base
    
    elif 'database' in low and ('ai' in low or 'sql' in low):
        base = 'เครื่องมือจัดการฐานข้อมูลและ SQL workspace ที่มี AI assistant ช่วยเขียน SQL จากภาษาธรรมดา อธิบาย query และ optimize'
        if '30' in full or 'mysql' in low:
            base += ' รองรับ 30+ databases: MySQL, PostgreSQL, Oracle, SQL Server, ClickHouse, MongoDB, Redis และอื่นๆ'
        if 'metadata' in low or 'ddl' in low:
            base += ' มี database management, browse metadata, edit data in place, import/export'
        return base
    
    elif 'terminal' in low and 'file' in low:
        base = 'โปรแกรมจัดการไฟล์สำหรับ terminal ที่มี UI สวยงามและใช้งานสะดวก'
        if 'keyboard' in low:
            base += ' รองรับ keyboard shortcuts, preview ไฟล์, และ operations ทั่วไปแบบ visual'
        if features:
            base += f' ฟีเจอร์: {features[:150]}'
        return base
    
    elif ('gui' in low or 'web gui' in low) and 'coding agent' in low:
        base = 'web GUI สำหรับ coding agents รองรับ Codex, Claude, Cursor, OpenCode ให้ใช้งาน AI coding assistant ผ่าน interface เดียว'
        if 'minimal' in low:
            base += ' ออกแบบให้เรียบง่าย เน้นใช้งานจริง'
        return base
    
    elif 'foundation model' in low or ('financial' in low and 'market' in low):
        base = 'foundation model ที่ออกแบบมาเฉพาะสำหรับข้อมูลตลาดการเงิน ใช้วิเคราะห์ลำดับเหตุการณ์และรูปแบบใน financial markets'
        if 'time series' in low or 'sequence' in low:
            base += ' ทำงานกับ time series data และทำนายแนวโน้ม'
        return base
    
    elif 'code review' in low:
        base = 'เครื่องมือ code review แบบ hybrid ใช้ทั้ง deterministic rules และ LLM agent ร่วมกัน ตรวจหา bugs, ช่องโหว่ความปลอดภัย และ code quality issues'
        if features:
            base += f' ฟีเจอร์: {features[:150]}'
        return base
    
    elif 'javascript runtime' in low or ('node' in low and 'runtime' in low):
        base = 'JavaScript runtime สำหรับฝั่ง server และ command line ใช้ V8 engine เป็นแกนหลักของ Node.js ecosystem ให้รัน JavaScript นอก browser'
        if 'open-source' in low:
            base += ' เป็น open-source และใช้ open governance model'
        return base
    
    elif 'minecraft' in low and 'server' in low:
        base = 'Minecraft server ที่เน้นความเร็วและประสิทธิภาพ เขียนด้วย Rust เพื่อลด resource usage และเพิ่มประสิทธิภาพการ host เกม'
        return base
    
    elif 'vpn' in low and 'client' in low:
        base = 'VPN client สำหรับ desktop และมือถือ ใช้เชื่อมต่อบริการ VPN'
        if 'amnezia' in low:
            base += ' รองรับ Amnezia VPN protocol'
        return base
    
    # Generic but comprehensive fallback
    sentences = [s for s in lines[:4] if len(s) > 40]
    if sentences:
        desc = ' '.join(sentences)[:350]
        # Clean up English into Thai context
        desc = re.sub(r'^(A |An |The )', '', desc)
        return f"โปรเจกต์นี้คือ {desc}"
    
    return None


def thai_summary(name, description, readme_md=None):
    # Priority 1: Manual curated
    if name in THAI_EXPLANATIONS:
        return THAI_EXPLANATIONS[name]

    # Priority 2: Extract from README
    if readme_md:
        extracted = extract_thai_description_from_readme(readme_md)
        if extracted:
            return extracted
    
    # Priority 3: Keyword fallback
    desc = (description or "").strip()
    low = desc.lower()
    for key, value in FALLBACK_THAI.items():
        if key in low:
            return value
    
    # Priority 4: Generic
    return f"โปรเจกต์จาก {name.split('/')[0]}: {desc}" if desc else None


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
        return None, None, None, None
    lines = clean_markdown(md)
    if not lines:
        return None, None, None, md

    what = first_matching_block(lines, README_HINTS['purpose'])
    usage = first_matching_block(lines, README_HINTS['usage'])
    purpose = first_matching_block(lines, README_HINTS['install'])

    summary = {
        'what_is_it': thai_summary(name, description, md) or what,
        'how_to_use': usage,
        'purpose': what,
    }
    formal_sections = summarize_readme_sections_th(md)
    if formal_sections:
        summary.update(formal_sections)
    return summary, '\\n'.join(lines[:80]), readme_image_url(name, md), md


FORMAL_REPLACEMENTS = [
    ('install', 'ติดตั้ง'), ('installation', 'การติดตั้ง'), ('quick start', 'การเริ่มต้นใช้งานอย่างรวดเร็ว'),
    ('getting started', 'การเริ่มต้นใช้งาน'), ('features', 'คุณสมบัติ'), ('feature', 'คุณสมบัติ'),
    ('usage', 'การใช้งาน'), ('overview', 'ภาพรวม'), ('database', 'ฐานข้อมูล'), ('server', 'เซิร์ฟเวอร์'),
    ('browser', 'เบราว์เซอร์'), ('agent', 'ตัวแทน AI'), ('workspace', 'พื้นที่ทำงาน'), ('self-hosted', 'ติดตั้งใช้งานบนระบบของตนเอง'),
    ('open-source', 'โอเพนซอร์ส'), ('runtime', 'รันไทม์'), ('framework', 'เฟรมเวิร์ก'), ('tool', 'เครื่องมือ'),
    ('code review', 'การตรวจทานโค้ด'), ('automation', 'ระบบอัตโนมัติ'), ('file manager', 'โปรแกรมจัดการไฟล์'),
    ('terminal', 'เทอร์มินัล'), ('command line', 'บรรทัดคำสั่ง'), ('sql workspace', 'พื้นที่ทำงาน SQL'),
]


def google_translate_th(text):
    """Translate English text to Thai using Google Translate free API."""
    if not text:
        return None
    text = ' '.join(str(text).replace('\\n', ' ').split())
    if len(text) < 10:
        return None
    # Truncate to avoid URL length limits
    if len(text) > 450:
        text = text[:447] + '...'
    try:
        import urllib.parse
        q = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={q}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = ""
            for sentence in data[0]:
                if sentence and sentence[0]:
                    result += sentence[0]
            return result if result else None
    except Exception:
        return None


def formal_thai(text):
    """Translate to formal Thai. Uses Google Translate, falls back to curated."""
    if not text:
        return None
    translated = google_translate_th(text)
    if translated:
        return translated
    # Fallback: basic word replacement
    out = ' '.join(str(text).replace('\\n', ' ').split())
    out = re.sub(r'AI agents', 'ตัวแทน AI', out, flags=re.I)
    out = re.sub(r'AI agent', 'ตัวแทน AI', out, flags=re.I)
    out = re.sub(r'database', 'ฐานข้อมูล', out, flags=re.I)
    out = re.sub(r'server', 'เซิร์ฟเวอร์', out, flags=re.I)
    out = re.sub(r'browser', 'เบราว์เซอร์', out, flags=re.I)
    return out


def summarize_readme_sections_th(md):
    if not md:
        return None
    lines = clean_markdown(md)
    if not lines:
        return None
    what = formal_thai(first_matching_block(lines, README_HINTS['purpose']))
    usage = formal_thai(first_matching_block(lines, README_HINTS['usage']))
    install = formal_thai(first_matching_block(lines, README_HINTS['install']))
    if install:
        install = re.sub(r'(npx|npm|pip|curl|brew|winget|cargo|git clone)[^\n]{0,220}', 'โปรดดูคำสั่งติดตั้งโดยตรงจาก README ต้นฉบับของโครงการ', install, flags=re.I)
    return {
        'what_is_it_formal_th': what,
        'how_to_use_formal_th': usage,
        'installation_formal_th': install,
    }


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
        readme_summary, readme_excerpt, readme_image, readme_md = summarize_readme_th(r["name"], r["description"])
        ordered.append({
            "rank": r["rank"], "name": r["name"], "description": r["description"],
            "thai_description": thai_summary(r["name"], r["description"], readme_md),
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
