#!/usr/bin/env python3
"""Build the study-notes site.

* For every note in notes-src/catalog.json that has a "source", turn the Markdown
  file into a single-page study guide (one hash-routed page per lecture).
* Rebuild index.html, the hub that lists every note.

Markdown conventions (the same ones the CS5242 notes use):
  #   document title (ignored)
  ##  top-level section -> one page, unless its title starts with an entry in
      the note config's "split" list; then each ### under it becomes a page
  **bold line**                  -> section heading inside a page
  *italic paragraph*             -> English translation of the paragraph above
  "中文 · English" in headings and table cells -> shown on two lines
  ```latex blocks               -> rendered with KaTeX at build time
  a heading containing 答案      -> its content is folded behind a "show" button;
      a question list followed by such a heading and an answer list is paired up

Requirements: Python packages markdown-it-py and beautifulsoup4 (with lxml),
and Node.js with the katex package (set KATEX_PATH if it is not on NODE_PATH).
Run from anywhere:  python3 tools/build_notes.py
"""
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent.parent
CJK = re.compile(r'[㐀-鿿豈-﫿]')
MD = MarkdownIt('commonmark', {'html': False}).enable('table')
SUMMARY_KEYS = ('一句话', '这一讲在干什么', '说明')
esc = html.escape


# ---------------------------------------------------------------- markdown

def split_sections(text):
    """Split Markdown into heading sections (levels 1-3), ignoring code fences."""
    sections, cur, fence = [], None, False
    for line in text.split('\n'):
        if line.startswith('```'):
            fence = not fence
        m = None if fence else re.match(r'^(#{1,3}) (.+?)\s*$', line)
        if m:
            cur = {'level': len(m.group(1)), 'title': m.group(2), 'lines': []}
            sections.append(cur)
        elif cur is not None:
            cur['lines'].append(line)
    return sections


def split_title(title):
    """'中文 · English' -> ('中文', 'English'); only splits when the right side has no CJK."""
    for m in re.finditer(r' · ', title):
        if CJK.search(title[:m.start()]) and not CJK.search(title[m.end():]):
            return title[:m.start()].strip(), title[m.end():].strip()
    return title.strip(), ''


def collect_pages(text, cfg):
    page_cfg = cfg['pages']
    pages, split_mode, current = [], False, None

    def match(title):
        for p in page_cfg:
            if title.startswith(p['match']):
                return p
        raise SystemExit(f'No page config matches heading: {title!r}')

    for sec in split_sections(text):
        lvl, title = sec['level'], sec['title']
        if lvl == 1:
            continue
        if lvl == 2:
            split_mode = any(title.startswith(s) for s in cfg.get('split', []))
            if split_mode:
                current = None
                continue
            current = {'cfg': match(title), 'title': title, 'md': sec['lines']}
            pages.append(current)
        elif lvl == 3:
            if split_mode:
                current = {'cfg': match(title), 'title': title, 'md': sec['lines']}
                pages.append(current)
            elif current is not None:
                current['md'] = current['md'] + ['', '## ' + title, ''] + sec['lines']
    return pages


# ---------------------------------------------------------------- html transforms

def element_children(el):
    return [c for c in el.children if isinstance(c, Tag)]


def sole_child(el):
    kids = [c for c in el.contents if not (isinstance(c, NavigableString) and not c.strip())]
    return kids[0] if len(kids) == 1 and isinstance(kids[0], Tag) else None


def split_bilingual(soup, el):
    """Wrap the English half of '中文 · English' (a direct text child) in span.en-inline."""
    full = el.get_text()
    cut = None
    for m in re.finditer(r' · ', full):
        if CJK.search(full[:m.start()]) and not CJK.search(full[m.end():]):
            cut = m.start()
            break
    if cut is None:
        return
    pos = 0
    for node in list(el.descendants):
        if not isinstance(node, NavigableString):
            continue
        n = len(node)
        if pos <= cut < pos + n:
            if node.parent is not el:
                return
            k = cut - pos
            before, after = str(node)[:k], str(node)[k + 3:]
            following = []
            sib = node.next_sibling
            while sib is not None:
                following.append(sib)
                sib = sib.next_sibling
            before_node = NavigableString(before)
            node.replace_with(before_node)
            span = soup.new_tag('span', attrs={'class': 'en-inline'})
            span.append(NavigableString(after))
            for f in following:
                span.append(f.extract())
            before_node.insert_after(span)
            return
        pos += n


def heading_text(h):
    span = h.find('span', class_='en-inline')
    return (h.get_text() if span is None else h.get_text().replace(span.get_text(), '')).strip()


def wrap(soup, elements, tag, **attrs):
    box = soup.new_tag(tag, attrs=attrs)
    elements[0].insert_before(box)
    for e in elements:
        box.append(e.extract())
    return box


def transform(fragment_html, page_id, formulas):
    soup = BeautifulSoup(f'<div id="root">{fragment_html}</div>', 'lxml')
    root = soup.find(id='root')

    # LaTeX code blocks -> placeholders filled in after KaTeX runs
    for pre in root.find_all('pre'):
        code = pre.find('code')
        if code and 'language-latex' in (code.get('class') or []):
            div = soup.new_tag('div', attrs={'class': 'math'})
            div.string = f'@@FORMULA{len(formulas)}@@'
            formulas.append(code.get_text().strip())
            pre.replace_with(div)

    # italic-only paragraphs are the English translations
    for p in root.find_all('p'):
        only = sole_child(p)
        if only is not None and only.name == 'em':
            p['class'] = ['en']
            only.unwrap()

    # bold-only top-level paragraphs, and bold-led lines without a translation, are headings
    for p in element_children(root):
        if p.name != 'p' or p.get('class'):
            continue
        only = sole_child(p)
        first = next((c for c in p.contents if not (isinstance(c, NavigableString) and not c.strip())), None)
        nxt = p.find_next_sibling()
        no_translation = not (nxt is not None and nxt.name == 'p' and 'en' in (nxt.get('class') or []))
        if (only is not None and only.name == 'strong') or (isinstance(first, Tag) and first.name == 'strong' and no_translation and ' · ' in p.get_text()):
            for s in p.find_all('strong'):
                s.unwrap()
            p.name = 'h3'
    heads = [h for h in element_children(root) if h.name in ('h2', 'h3')]
    numbered = any(re.match(r'^\d+\.', h.get_text()) for h in heads if h.name == 'h3')
    for h in heads:
        if h.name == 'h3' and (not numbered or re.match(r'^\d+\.', h.get_text())):
            h.name = 'h2'

    # two-line bilingual headings and table cells; tables scroll on small screens
    for el in root.find_all(['h2', 'h3', 'td', 'th']):
        split_bilingual(soup, el)
    for t in root.find_all('table'):
        wrap(soup, [t], 'div', **{'class': 'table-wrap'})

    # summary box: "这一讲在干什么 / 一句话 / 说明" paragraph plus its translation
    for p in element_children(root):
        if p.name == 'p' and not p.get('class'):
            first = next((c for c in p.contents if not (isinstance(c, NavigableString) and not c.strip())), None)
            if isinstance(first, Tag) and first.name == 'strong' and first.get_text().strip() in SUMMARY_KEYS:
                group = [p]
                nxt = p.find_next_sibling()
                if nxt is not None and 'en' in (nxt.get('class') or []):
                    group.append(nxt)
                wrap(soup, group, 'div', **{'class': 'summary'})

    # pair question lists with their answer lists
    def is_answer_heading(h):
        return h is not None and h.name in ('h2', 'h3') and heading_text(h).startswith('答案')
    paired = True
    while paired:
        paired = False
        for q in element_children(root):
            h = q.find_next_sibling() if q.name == 'ol' else None
            a = h.find_next_sibling() if is_answer_heading(h) else None
            if a is None or a.name != 'ol':
                continue
            qs, ans = q.find_all('li', recursive=False), a.find_all('li', recursive=False)
            if len(qs) != len(ans):
                continue
            for qi, ai in zip(qs, ans):
                det = soup.new_tag('details', attrs={'class': 'answer'})
                summ = soup.new_tag('summary')
                summ.string = '看答案 · Answer'
                inner = soup.new_tag('div')
                for c in list(ai.contents):
                    inner.append(c.extract())
                det.append(summ)
                det.append(inner)
                qi.append(det)
            h.decompose()
            a.decompose()
            paired = True
            break
    # fold every other answer section behind a button
    def is_fold_heading(h):
        t = heading_text(h)
        return t.startswith('答案') or re.search(r'Quiz\s*\d+\s*答案', t)
    for h in [h for h in element_children(root) if h.name in ('h2', 'h3') and is_fold_heading(h)]:
        level = int(h.name[1])
        group, sib = [], h.find_next_sibling()
        while sib is not None and not (sib.name in ('h2', 'h3') and int(sib.name[1]) <= level):
            group.append(sib)
            sib = sib.find_next_sibling()
        if group:
            det = wrap(soup, group, 'details', **{'class': 'reveal'})
            inner = soup.new_tag('div')
            for c in list(det.contents):
                inner.append(c.extract())
            summ = soup.new_tag('summary')
            summ.string = '点开看答案与步骤 · Show answers and steps'
            det.append(summ)
            det.append(inner)

    # common-mistakes boxes
    for h in [h for h in element_children(root) if h.name in ('h2', 'h3') and '易错点' in heading_text(h)]:
        nxt = h.find_next_sibling()
        wrap(soup, [h] + ([nxt] if nxt is not None and nxt.name in ('ul', 'ol') else []), 'div', **{'class': 'pitfall'})

    # anchors for the in-page table of contents
    toc = []
    for n, h in enumerate(root.find_all('h2'), 1):
        h['id'] = f'{page_id}-s{n}'
        toc.append((h['id'], heading_text(h)))

    summary = ''
    boxes = {b.find('strong').get_text().strip(): b.find('p').get_text() for b in root.find_all('div', class_='summary')}
    for key in SUMMARY_KEYS:
        if key in boxes:
            summary = boxes[key]
            break
    return root, toc, summary


def render_formulas(formulas):
    if not formulas:
        return []
    env = dict(os.environ)
    if 'KATEX_PATH' not in env:
        for guess in ('/opt/npm-tools/node_modules/katex', str(ROOT / 'node_modules' / 'katex')):
            if Path(guess).exists():
                env['KATEX_PATH'] = guess
                break
    proc = subprocess.run(['node', str(ROOT / 'tools' / 'katex_render.js')], input=json.dumps(formulas),
                          capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise SystemExit('KaTeX rendering failed:\n' + proc.stderr)
    out = json.loads(proc.stdout)
    bad = [(i, o['error']) for i, o in enumerate(out) if not o['ok']]
    for i, err in bad:
        print(f'  ! formula {i} fell back to plain TeX: {err}', file=sys.stderr)
    return out


# ---------------------------------------------------------------- page assembly

def short_summary(text):
    text = re.sub(r'^\S{1,8}：', '', text.strip())
    first = re.split(r'(?<=[。；])', text)[0]
    if len(first) > 64:
        first = first[:62].rstrip('，、；：') + '…'
    return first


def build_note(note, catalog):
    cfg = json.loads((ROOT / note['config']).read_text(encoding='utf-8'))
    text = (ROOT / note['source']).read_text(encoding='utf-8')
    raw_pages = collect_pages(text, cfg)
    formulas, pages = [], []
    for rp in raw_pages:
        pc = rp['cfg']
        frag = MD.render('\n'.join(rp['md']))
        root, toc, summary = transform(frag, pc['id'], formulas)
        zh, en = split_title(rp['title'])
        pages.append({'cfg': pc, 'zh': zh, 'en': en, 'root': root, 'toc': toc, 'summary': summary})

    rendered = render_formulas(formulas)

    def fill_formulas(markup):
        def sub(m):
            i = int(m.group(1))
            return rendered[i]['html'] if rendered[i]['ok'] else f'<pre>{esc(formulas[i])}</pre>'
        return re.sub(r'@@FORMULA(\d+)@@', sub, markup)

    by_id = {p['cfg']['id']: p for p in pages}
    order = ['overview'] + [pid for g in cfg['groups'] for pid in g['pages'] if pid != 'overview']
    missing = [pid for pid in order[1:] if pid not in by_id]
    if missing:
        raise SystemExit(f'Groups list pages that were not found in the notes: {missing}')
    lecture_ids = [pid for pid in order if pid in by_id and by_id[pid]['cfg'].get('lecture')]

    def nav_title(pid):
        return '复习总览' if pid == 'overview' else by_id[pid]['zh']

    # sidebar
    nav = []
    for g in cfg['groups']:
        nav.append(f'<div class="navlabel">{esc(g["label"])}</div>')
        for pid in g['pages']:
            if pid == 'overview':
                nav.append('<a href="#overview" data-page="overview"><span class="num">◉</span>复习总览</a>')
                continue
            pc = by_id[pid]['cfg']
            done = '<span class="done"></span>' if pc.get('lecture') else ''
            nav.append(f'<a href="#{pid}" data-page="{pid}"><span class="num">{esc(pc["num"])}</span>{esc(pc["nav"])}{done}</a>')

    # overview page
    selftest_count = 0
    if 'selftest' in by_id:
        selftest_count = len(by_id['selftest']['root'].find_all('details', class_='answer'))
    quiz_count = sum(1 for p in pages for h in p['root'].find_all(['h2', 'h3']) if re.match(r'^Quiz \d+', heading_text(h)))
    n_lectures = sum(1 for pid in lecture_ids if re.match(r'^L\d+$', pid))
    cards = []
    for pid in order[1:]:
        p = by_id[pid]
        pc = p['cfg']
        n_f = len(p['root'].find_all('div', class_='math'))
        quiz = any(re.match(r'^Quiz \d+', heading_text(h)) for h in p['root'].find_all(['h2', 'h3']))
        desc = pc.get('desc') or (short_summary(p['summary']) if p['summary'] else (p['en'] or ''))
        bits = [f'{n_f} 个公式'] if n_f else []
        if quiz:
            bits.append('Quiz 解析')
        if not bits:
            bits.append('速查' if not pc.get('lecture') else '概念')
        title = re.sub(r'^L\d+\s+', '', p['zh'])
        cards.append(f'<a class="chapter-card" href="#{pid}"><div class="cardtop"><span class="index">{esc(pc["num"])}</span>'
                     f'<span>{esc(pc.get("tag", ""))}</span></div><h3>{esc(title)}</h3>'
                     f'<p>{esc(desc)}</p><div class="cardbottom"><span>{" · ".join(bits)}</span><span>↗</span></div></a>')
    hero = cfg['hero']
    overview = (
        '<section class="page" id="overview" data-title="复习总览">'
        f'<div class="hero"><div class="eyebrow">{esc(hero["eyebrow"])}</div><h1>{hero["title"]}</h1><p>{esc(hero["text"])}</p>'
        '<button class="primary" id="start" type="button">开始复习 →</button>'
        f'<div class="metrics"><div><b>{n_lectures:02d}</b><span>讲</span></div><div><b>{len(formulas)}</b><span>个公式</span></div>'
        f'<div><b>{quiz_count}</b><span>套 Quiz 解析</span></div><div><b>{selftest_count}</b><span>道自测</span></div></div></div>'
        f'<p class="intro-note">{esc(hero["note"])}</p>'
        '<div class="sectionhead"><h2>按讲复习，最后做自测</h2><small>点卡片进入；右上角可以只看中文</small></div>'
        f'<div class="chapter-grid">{"".join(cards)}</div></section>'
    )

    # content pages
    sections = [overview]
    for idx, pid in enumerate(order[1:], 1):
        p = by_id[pid]
        pc = p['cfg']
        if pc.get('lecture') and re.match(r'^L\d+$', pid):
            eyebrow = f'LECTURE {pc["num"]}'
        elif pc.get('lecture'):
            eyebrow = (p['en'].split('(')[0].strip() or pid).upper()
        else:
            eyebrow = f'{cfg["code"]} / {(p["en"] or pid).split(":")[0].upper()}'
        head = (f'<header class="lesson-head"><div class="eyebrow">{esc(eyebrow)}</div><h1>{esc(re.sub(r"^L\d+\s+", "", p["zh"]))}</h1>'
                + (f'<p class="en-sub en">{esc(p["en"])}</p>' if p['en'] else '') + '</header>')
        toc = ''
        if len(p['toc']) >= 3:
            toc = ('<p class="toc-label">本页目录</p><div class="toc">'
                   + ''.join(f'<button type="button" data-jump="{tid}">{esc(re.sub(r"^(\d+)\.\s*", r"\1 ", t))}</button>' for tid, t in p['toc'])
                   + '</div>')
        prev_id, next_id = order[idx - 1], order[idx + 1] if idx + 1 < len(order) else None
        complete = f'<button class="complete-btn" type="button" data-complete="{pid}" aria-pressed="false">标记本讲已复习</button>' if pc.get('lecture') else '<span></span>'
        footer = (f'<div class="lesson-footer"><a href="#{prev_id}">← {esc(nav_title(prev_id))}</a>{complete}'
                  + (f'<a href="#{next_id}">{esc(nav_title(next_id))} →</a>' if next_id else '<a href="index.html">全部笔记 →</a>')
                  + '</div>')
        lecture_attr = ' data-lecture="1"' if pc.get('lecture') else ''
        sections.append(f'<section class="page lesson" id="{pid}" data-title="{esc(p["zh"])}"{lecture_attr} hidden>'
                        f'{head}{toc}{fill_formulas(p["root"].decode_contents())}{footer}</section>')

    accent = f'accent-{cfg.get("accent", "green")}'
    page_html = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{esc(cfg["description"])}">
<title>{esc(cfg["title"])}</title>
<link rel="stylesheet" href="assets/katex/katex.min.css">
<link rel="stylesheet" href="assets/site.css">
</head>
<body class="{accent}" data-store="{esc(cfg["store"])}" data-code="{esc(cfg["code"])}">
<a class="skip" href="#main">跳到正文</a>
<aside id="sidebar" aria-label="课程导航">
 <a class="back-link" href="index.html">← 全部笔记</a>
 <div class="brand"><span class="brandmark" aria-hidden="true">{esc(cfg["brandmark"])}</span><div><strong>{esc(cfg["code"])}</strong><small>{esc(cfg["brand_small"])}</small></div></div>
 <nav id="nav" aria-label="{esc(cfg["subject"])}">{"".join(nav)}</nav>
 <div class="sidebar-foot"><div id="progress-text">你的复习进度 · 0 / {len(lecture_ids)}</div><div class="progressbar" role="progressbar" aria-label="复习进度" aria-valuemin="0" aria-valuemax="{len(lecture_ids)}" aria-valuenow="0"><span id="progress-fill" style="width:0%"></span></div><p style="font-size:11px;margin:8px 0 0">{cfg["foot_note"]}</p></div>
</aside>
<div class="workspace">
<header class="topbar"><button class="menu-toggle" type="button" aria-controls="sidebar" aria-expanded="false">目录</button><div class="crumb">{esc(cfg["code"])} <span style="padding:0 8px">/</span><b id="breadcrumb">复习总览</b></div><div class="searchbox"><label for="search" hidden>搜索知识点</label><input id="search" type="search" placeholder="搜索概念、公式或题目…" autocomplete="off" aria-controls="search-results"><div id="search-results" class="search-results" hidden></div></div><button class="tool" id="lang-toggle" type="button" aria-pressed="false">只看中文</button><button class="tool" id="print" type="button">打印讲义</button></header>
<main class="content" id="main">
{chr(10).join(sections)}
</main>
<footer class="footer">{esc(catalog["site"]["footer"])} 公式由 KaTeX 渲染。</footer>
</div>
<script src="assets/notes.js"></script>
</body>
</html>
'''
    out = ROOT / cfg['out']
    out.write_text(page_html, encoding='utf-8')
    print(f'built {out.name}: {len(pages)} pages, {len(formulas)} formulas, {selftest_count} self-test questions')


def build_hub(catalog):
    site = catalog['site']
    cards = []
    for n in catalog['notes']:
        links = ''.join(f'<a href="{esc(l["href"])}"{" class=\"primary\"" if l.get("primary") else ""}>{esc(l["label"])}{" →" if l.get("primary") else ""}</a>' for l in n['links'])
        chips = ''.join(f'<li>{esc(c)}</li>' for c in n.get('chips', []))
        cards.append(f'<article class="course-card accent-{esc(n.get("accent", "green"))}">'
                     f'<div class="course-top"><span class="course-code">{esc(n["code"])}</span><span>{esc(n["scope"])}</span></div>'
                     f'<h2>{esc(n["title"])}</h2><p class="en-sub">{esc(n["title_en"])}</p>'
                     f'<p class="course-summary">{esc(n["summary"])}</p><ul class="chips">{chips}</ul>'
                     f'<div class="course-links">{links}</div><div class="course-foot">更新于 {esc(n["updated"])}</div></article>')
    # Old links pointed the site root at the CS5228 guide; keep its section hashes working.
    legacy = [n for n in catalog['notes'] if n['id'] == 'cs5228']
    redirect = ''
    if legacy:
        redirect = ('<script>(function(){var h=location.hash;if(/^#(overview|lecture[1-6]|review|cheat-sheet)$/.test(h))'
                    f'location.replace({json.dumps(legacy[0]["href"])}+h)}})();</script>')
    hub = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{esc(site["tagline"])}">
<title>{esc(site["title"])} · {esc(site["title_en"])}</title>
<link rel="stylesheet" href="assets/site.css">
{redirect}
</head>
<body>
<main class="hub">
 <div class="hub-brand"><span class="brandmark" aria-hidden="true">∴</span><div><strong>{esc(site["title_en"].upper())}</strong><small>NUS COURSE COMPANIONS</small></div></div>
 <section class="hub-hero">
  <div class="eyebrow" style="color:#315b47">STUDY NOTES / 复习笔记集</div>
  <h1>每门课一本手册，<br><span>考前都在这里。</span></h1>
  <p>{esc(site["tagline"])}</p>
  <p class="en-sub">{esc(site["tagline_en"])}</p>
  <div class="hub-metrics"><div><b>{len(catalog["notes"]):02d}</b><span>门课程</span></div><div><b>{sum(n.get("stats", {}).get("lectures", 0) for n in catalog["notes"])}</b><span>讲</span></div><div><b>{sum(n.get("stats", {}).get("selftests", 0) for n in catalog["notes"])}</b><span>道自测</span></div></div>
 </section>
 <div class="sectionhead"><h2>课程笔记</h2><small>按最近更新排列</small></div>
 <div class="course-grid">
 {"".join(cards)}
 </div>
 <p class="hub-foot">{esc(site["footer"])}</p>
</main>
</body>
</html>
'''
    (ROOT / 'index.html').write_text(hub, encoding='utf-8')
    print(f'built index.html: {len(cards)} notes')


def main():
    catalog = json.loads((ROOT / 'notes-src' / 'catalog.json').read_text(encoding='utf-8'))
    for note in catalog['notes']:
        if note.get('source'):
            build_note(note, catalog)
    build_hub(catalog)


if __name__ == '__main__':
    main()
