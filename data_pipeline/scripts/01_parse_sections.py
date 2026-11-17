#!/usr/bin/env python3
"""Parse the four PRISM pilot files. Python 3.9+, standard library only.

Sections are contiguous, non-overlapping source spans split at ATX headings
and HTML disclosure boundaries. These are structural sections, not final KOs.
raw_text preserves original line endings; line numbers are 1-based inclusive.
Front matter and whitespace-only gaps are omitted. IDs are deterministic for
an unchanged snapshot, NOT persistent identities across edited snapshots.
"""
import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

FILES = {
    'bv-benefits-netherlands.md': 'NL',
    'general-and-entity-benefits__index.md': 'GLOBAL',
    'leave-types.md': 'LEAVE',
    'ltd-benefits-uk.md': 'UK',
}
HEADING = re.compile(r'^ {0,3}(#{1,6})\s+(.+?)\s*$')
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
DETAIL = re.compile(r'<(/?)details\b[^>]*>', re.I)
SUMMARY = re.compile(r'<summary\b[^>]*>(.*?)</summary\s*>', re.I | re.S)
REF = re.compile(r'^ {0,3}\[([^\]]+)\]:\s*(?:<([^>]+)>|(\S+))')


def plain(text):
    return html.unescape(re.sub(r'<[^>]+>', '', text)).strip()


def norm_ref(text):
    return ' '.join(text.casefold().split())


def visible_source(lines):
    """Mask code/comments without changing offsets (for links and structure)."""
    result = []
    fence = None
    comment = False
    for line in lines:
        m = FENCE.match(line)
        if fence:
            result.append(re.sub(r'[^\r\n]', ' ', line))
            if m and m[1][0] == fence[0] and len(m[1]) >= len(fence) and not line[m.end():].strip():
                fence = None
            continue
        if m and not comment:
            fence = m[1]
            result.append(re.sub(r'[^\r\n]', ' ', line))
            continue
        chars = list(line)
        i = 0
        while i < len(line):
            if comment:
                end = line.find('-->', i)
                stop = len(line) if end < 0 else end + 3
                for j in range(i, stop):
                    if chars[j] not in '\r\n': chars[j] = ' '
                i = stop
                if end >= 0: comment = False
            elif line.startswith('<!--', i):
                comment = True
            else:
                i += 1
        clean = ''.join(chars)
        clean = re.sub(r'(`+)(.+?)\1', lambda m: ' ' * len(m[0]), clean)
        result.append(clean)
    return result


def extract_links(lines, start, references):
    """Inline/reference Markdown links, angle autolinks, and HTML anchors.

    Handles balanced URL parentheses. URLs remain unresolved. Image embeds
    and bare URLs are not outgoing links. Link positions refer to their start.
    """
    text = ''.join(lines)
    hits = []
    occupied = []
    def add(pos, end, label, url):
        hits.append((pos, {'anchor_text': plain(label), 'target_url': html.unescape(url),
                           'line_number': start + text.count('\n', 0, pos)}))
        occupied.append((pos, end))
    pattern = re.compile(r'(?<![!\\])\[((?:\\.|[^\]\\])+)\]')
    for m in pattern.finditer(text):
        if any(a <= m.start() < b for a,b in occupied): continue
        p = m.end()
        if p < len(text) and text[p] == ':': continue  # reference definition
        if p < len(text) and text[p] == '(':
            p += 1
            while p < len(text) and text[p].isspace(): p += 1
            begin = p
            if p < len(text) and text[p] == '<':
                end = text.find('>', p + 1)
                if end < 0: continue
                url = text[p+1:end]; p = end + 1
            else:
                depth = 0
                while p < len(text):
                    c = text[p]
                    if c == '\\' and p+1 < len(text): p += 2; continue
                    if c == '(' : depth += 1
                    elif c == ')':
                        if depth == 0: break
                        depth -= 1
                    elif c.isspace() and depth == 0: break
                    p += 1
                url = text[begin:p]
            # Optional link title in quotes or parentheses.
            tail = re.match(r'\s*(?:(?:"[^"]*"|\x27[^\x27]*\x27|\([^)]*\))\s*)?\)', text[p:])
            if tail:
                add(m.start(), p+tail.end(), m[1], re.sub(r'\\([()])', r'\1', url))
        else:
            ref = re.match(r'\[([^\]]*)\]', text[p:])
            key = (ref[1] or m[1]) if ref else m[1]
            if norm_ref(key) in references:
                add(m.start(), p+(ref.end() if ref else 0), m[1], references[norm_ref(key)])
    for m in re.finditer(r'<a\b[^>]*href\s*=\s*(["\x27])(.*?)\1[^>]*>(.*?)</a\s*>', text, re.I|re.S):
        add(m.start(),m.end(),m[3],m[2])
    for m in re.finditer(r'<((?:https?://|mailto:)[^<>\s]+|[^<>\s@]+@[^<>\s@]+\.[^<>\s@]+)>',text):
        if not any(a <= m.start() < b for a,b in occupied):
            url=m[1] if ':' in m[1] else 'mailto:'+m[1]
            add(m.start(),m.end(),m[1],url)
    return [item for _,item in sorted(hits,key=lambda x:x[0])]


def parse_file(path, prefix):
    data = path.read_bytes()
    text = data.decode('utf-8')  # no universal-newline conversion
    lines = text.splitlines(keepends=True)
    masked = visible_source(lines)
    sha = hashlib.sha256(data).hexdigest()
    title = path.stem
    body = 0
    if lines and lines[0].lstrip('\ufeff').strip() == '---':
        end = next((i for i in range(1,len(lines)) if lines[i].strip() in ('---','...')), None)
        if end is None: raise ValueError(f'{path.name}: unclosed YAML front matter')
        for line in lines[1:end]:
            m = re.match(r'^title:\s*(.*?)\s*$', line)
            if m: title = m[1].strip('"\x27')
        body = end+1
    refs = {}
    for line in masked[body:]:
        m = REF.match(line)
        if m: refs[norm_ref(m[1])] = m[2] or m[3]
    # Match disclosure tags first so headings inside valid disclosures survive.
    pending, matched = [], set()
    for n, line in enumerate(masked):
        for tag in DETAIL.finditer(line):
            if not tag[1]: pending.append(n)
            elif pending: matched.add(pending.pop())
    sections, warnings = [], []
    headings, disclosures = [], []
    start = body
    def emit(end):
        nonlocal start
        a,b=start,end
        while a<b and not lines[a].strip(): a+=1
        while b>a and not lines[b-1].strip(): b-=1
        if a<b:
            sections.append({
                'section_id': f'SEC_{prefix}_{len(sections)+1:02d}',
                'source_file': path.name, 'source_sha256': sha,
                'heading_path': [title]+[h for _,h in headings],
                'disclosure_title': disclosures[-1][0] if disclosures else None,
                'line_start': a+1, 'line_end': b,
                'raw_text': ''.join(lines[a:b]),
                'outgoing_links': extract_links(masked[a:b],a+1,refs),
            })
        start=end
    i=body
    while i<len(lines):
        h=HEADING.match(masked[i])
        tags=list(DETAIL.finditer(masked[i]))
        if h:
            emit(i)
            if disclosures and any(d[2] not in matched for d in disclosures):
                warnings.append(f'{path.name}:{i+1}: unclosed details reset at heading')
                disclosures.clear()
            level=len(h[1]); name=re.sub(r'\s+#+\s*$', '', h[2])
            while headings and headings[-1][0]>=level: headings.pop()
            headings.append((level,plain(name)))
        if tags:
            # Pilot disclosures open/close on separate lines. Refuse ambiguous
            # inline combinations instead of assigning incorrect context.
            if len(tags)>1: raise ValueError(f'{path.name}:{i+1}: multiple details tags on one line')
            if not tags[0][1]:
                emit(i)
                j=i+1
                while j<len(lines) and not HEADING.match(masked[j]) and not DETAIL.search(masked[j]): j+=1
                summary=SUMMARY.search(''.join(masked[i:j]))
                if not summary: warnings.append(f'{path.name}:{i+1}: details has no summary')
                disclosures.append((plain(summary[1]) if summary else None, list(headings), i))
            else:
                emit(i+1)
                if disclosures:
                    _, saved_headings, _ = disclosures.pop()
                    headings[:] = saved_headings
                else: warnings.append(f'{path.name}:{i+1}: unmatched closing details')
        i+=1
    emit(len(lines))
    if disclosures: warnings.append(f'{path.name}: unclosed details at EOF')
    # Validate exact source spans, disjointness, and complete nonblank body coverage.
    covered=set()
    for s in sections:
        a,b=s['line_start']-1,s['line_end']
        assert s['raw_text']==''.join(lines[a:b])
        span=set(range(a,b)); assert not (span & covered); covered.update(span)
        assert all(a+1<=l['line_number']<=b for l in s['outgoing_links'])
    assert all(i in covered or not lines[i].strip() for i in range(body,len(lines)))
    return sections,warnings


def main():
    base=Path(__file__).resolve().parents[1]
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input-dir',type=Path,default=base/'raw_pilot')
    ap.add_argument('--output',type=Path,default=base/'artifacts'/'parsed_sections.json')
    args=ap.parse_args()
    missing=[name for name in FILES if not (args.input_dir/name).is_file()]
    if missing: ap.error('Missing input files: '+', '.join(missing))
    result=[]; warnings=[]
    for name,prefix in FILES.items():
        sections,notes=parse_file(args.input_dir/name,prefix)
        result.extend(sections); warnings.extend(notes)
        print(f'{name}: {len(sections)} sections, {sum(len(s["outgoing_links"]) for s in sections)} links')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Total: {len(result)} sections -> {args.output}')
    for note in warnings: print('WARNING: '+note,file=sys.stderr)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
