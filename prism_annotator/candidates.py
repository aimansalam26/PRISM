"""Deterministic unordered nominations. No semantic dependency claim or model call."""
import json,time,re,unicodedata
from collections import defaultdict
from itertools import combinations
from urllib.parse import urlsplit,unquote
from graph_store import fingerprint

VERSION='candidates-2'

def slug(text):
    text=re.sub(r'\s*\{#[^}]+\}\s*$','',text)
    text=re.sub(r'<[^>]+>','',text).lower()
    return re.sub(r'[^\w\s-]','',text).strip().replace(' ','-')

def field_tokens(field):
    aliases={'limit':'cap','threshold':'cap','ceiling':'cap','bicycle':'bike','stipend':'allowance','healthcare':'medical','health':'medical'}
    stop={'eur','usd','gbp','amount','value','policy','rule','the','to','of','in','for','days','monthly','annual'}
    return {aliases.get(t,t) for t in re.findall(r'[a-z]+',field.lower()) if t not in stop}


def page_path(value):
    path=unquote(urlsplit(str(value).replace('\\','/')).path)
    if '/handbook/' not in path:return None
    path='/handbook/'+path.split('/handbook/',1)[1]
    if path.endswith('.md'):path=path[:-3]
    if path.endswith('/_index'):path=path[:-7]
    return path.rstrip('/')

def generate(nodes,diagnostics=None):
    diagnostics=diagnostics if diagnostics is not None else []
    nodes=[n for n in nodes if n['ko'].get('status') not in ['rejected','deleted'] and not n.get('errors')]
    lookup={n['key']:n for n in nodes};buckets=defaultdict(set);pages=defaultdict(set);pairs=defaultdict(set)
    for n in nodes:
        k=n['ko'];path=tuple(n.get('section',{}).get('heading_path') or k.get('heading_path',[]))
        if path:buckets[('topic',n['project'],path)].add(n['key'])
        for field in k.get('watched_fields',[]):
            if field.strip().lower() not in ['unknown','unspecified','value','amount']:buckets[('field',field)].add(n['key'])
        tokens=set().union(*(field_tokens(f) for f in k.get('watched_fields',[])))
        for pair in combinations(sorted(tokens),2):buckets[('lexical',pair)].add(n['key'])
        page=page_path(n['source_file'])
        if page:pages[page].add(n['key'])
    for bucket,keys in buckets.items():
        reason='Same full topic path in one source' if bucket[0]=='topic' else ('Shared watched field: '+bucket[1] if bucket[0]=='field' else 'Field-token overlap (nomination only): '+', '.join(bucket[1]))
        for a,b in combinations(sorted(keys),2):pairs[a,b].add(reason)
    for n in nodes:
        for link in n.get('section',{}).get('outgoing_links',[]):
            url=link.get('target_url','');parsed=urlsplit(url)
            if parsed.netloc and parsed.netloc not in ['handbook.gitlab.com','about.gitlab.com']:continue
            page=page_path(url) if parsed.path else page_path(n['source_file'])
            targets=pages.get(page,set());fragment=unquote(parsed.fragment)
            signal='Document hyperlink (not proof of dependency): '+url
            if fragment:
                explicit_sections={lookup[key]['section'].get('section_id') for key in targets if fragment in re.findall(r'''(?:id|name)=["']([^"']+)["']''',lookup[key]['section'].get('raw_text',''))}
                if len(explicit_sections)==1:
                    chosen=next(iter(explicit_sections))
                    targets={key for key in targets if lookup[key]['section'].get('section_id')==chosen}
                    for other in targets:
                        if other!=n['key']:pairs[tuple(sorted([n['key'],other]))].add('Explicit HTML anchor matched in target section: '+url)
                    continue
                if len(explicit_sections)>1:
                    diagnostics.append('Duplicate explicit anchor; inspect manually: '+url);continue
                paths=set()
                for key in targets:
                    target=lookup[key];path=target['section'].get('heading_path',[])
                    for i,h in enumerate(path):
                        explicit=re.search(r'\{#([^}]+)\}',h)
                        if fragment==(explicit.group(1) if explicit else slug(h)):paths.add(tuple(path[:i+1]))
                if len(paths)!=1:
                    diagnostics.append('Unresolved or ambiguous fragment; no document-wide fallback: '+url);continue
                prefix=next(iter(paths))
                targets={key for key in targets if tuple(lookup[key]['section'].get('heading_path',[])[:len(prefix)])==prefix}
                signal='Heading-fragment match (heading subtree; verify rendered anchor): '+url
            if not targets:diagnostics.append('No loaded target KOs for link: '+url)
            for other in targets:
                if other!=n['key']:pairs[tuple(sorted([n['key'],other]))].add(signal)
    out=[]
    for (a,b),reasons in sorted(pairs.items()):
        versions={key:lookup[key]['fingerprint'] for key in [a,b]}
        out.append({'id':'CAND_'+fingerprint([a,b])[:20],'a':a,'b':b,'signals':sorted(reasons),'fingerprint':fingerprint([VERSION,versions,sorted(reasons)]),'cross_document':lookup[a]['project']!=lookup[b]['project']})
    return out

def report(graph):
    graph.db.execute('CREATE TABLE IF NOT EXISTS candidate_reviews (id TEXT PRIMARY KEY,body TEXT)');graph.db.commit()
    state=graph.state();diagnostics=[];rows=generate(state['nodes'],diagnostics)
    saved={r[0]:json.loads(r[1]) for r in graph.db.execute('SELECT id,body FROM candidate_reviews')}
    for row in rows:
        r=saved.get(row['id']);row['review']=r
        row['status']=r['decision'] if r and r['fingerprint']==row['fingerprint'] else 'pending'
        row['stale_review']=bool(r and r['fingerprint']!=row['fingerprint'])
        row['edges']=[e['id'] for e in state['edges'] if {e['source'],e['target']}=={row['a'],row['b']} and e['status']!='rejected']
    return {'version':VERSION,'candidates':rows,'nodes':state['nodes'],'warnings':state['warnings']+sorted(set(diagnostics)),'notice':'Unordered suggestions only. Signals are not dependencies. Unnominated pairs may still be related; use manual graph connections. Unknown scopes are not pruned.'}

def review(graph,p,reviewer):
    row=next((r for r in report(graph)['candidates'] if r['id']==p.get('id')),None)
    if not row or row['fingerprint']!=p.get('fingerprint'):raise ValueError('Candidate changed; refresh before reviewing.')
    if p.get('decision') not in ['no_dependency','needs_context','pending']:raise ValueError('Invalid decision.')
    p=dict(p);p['note']=str(p.get('note','')).strip() or 'Pair decision selected: '+p['decision']+'. No free-text explanation supplied.'
    value={k:p[k] for k in ['id','fingerprint','decision','note']};value.update(reviewer=reviewer,time=time.time())
    old=graph.db.execute('SELECT body FROM candidate_reviews WHERE id=?',(row['id'],)).fetchone()
    with graph.db:
        graph.db.execute('INSERT OR REPLACE INTO candidate_reviews VALUES (?,?)',(row['id'],json.dumps(value)))
        graph.db.execute('INSERT INTO audit VALUES (?,?,?,?,?)',(time.time(),reviewer,row['id'],old[0] if old else None,json.dumps(value)))
    return value

if __name__=='__main__':
    import argparse
    from pathlib import Path
    from graph_store import GraphStore
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',required=True);ap.add_argument('--output',required=True);args=ap.parse_args()
    graph=GraphStore(args.workspace)
    try:
        result=report(graph);Path(args.output).write_text(json.dumps(result,indent=2),encoding='utf-8');print(f"{len(result['candidates'])} unordered candidate pairs saved. No edges created.")
    finally:graph.db.close()
