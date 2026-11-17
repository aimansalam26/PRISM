"""Evidence, per-unit human coverage, requirement groups, and staged reruns."""
import json,re,time,secrets
from graph_store import fingerprint

def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS unit_reviews(id TEXT PRIMARY KEY,body TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS rerun_proposals(id TEXT PRIMARY KEY,body TEXT)');db.commit()

def add_document_context(data,sections):
    """Keep YAML evidence addressable without turning it into extracted rules.
    Existing policy section IDs are unchanged; one context-only record is appended.
    """
    if not sections:return sections
    lines=data.decode('utf-8').splitlines(keepends=True)
    if not lines or lines[0].lstrip('\ufeff').strip()!='---':return sections
    end=next((i for i in range(1,len(lines)) if lines[i].strip() in ['---','...']),None)
    if end is None:return sections
    s=sections[0]
    return sections+[{'section_id':'CTX_'+s['source_sha256'][:16],'source_file':s['source_file'],'source_sha256':s['source_sha256'],'heading_path':s.get('heading_path',[])[:1],'disclosure_title':None,'line_start':1,'line_end':end+1,'raw_text':''.join(lines[:end+1]),'outgoing_links':[],'context_only':True}]

def context_options(section,sections):
    path=section.get('heading_path',[]);out=[]
    # Exact source references only. Metadata titles without source text are not evidence.
    for s in sorted(sections,key=lambda x:(not x.get('context_only',False),x['line_start'])):
        sp=s.get('heading_path',[])
        if s['section_id']!=section['section_id'] and not (sp==path or (sp and path[:len(sp)]==sp)):continue
        for offset,line in enumerate(s['raw_text'].splitlines()):
            if not line.strip():continue
            if s['section_id']!=section['section_id'] and not (line.lstrip().startswith('#') or s.get('disclosure_title') is None):continue
            out.append({'section_id':s['section_id'],'quote':line,'line_start':s['line_start']+offset,'source_file':s['source_file'],'purpose':'subject'})
    return out

def audit(db,ident,before,after,reviewer):
    db.execute('INSERT INTO audit VALUES (?,?,?,?,?)',(time.time(),reviewer,ident,json.dumps(before) if before else None,json.dumps(after)))

def unit_state(db,units,kos):
    init(db);saved={r[0]:json.loads(r[1]) for r in db.execute('SELECT id,body FROM unit_reviews')};out=[]
    for u in units:
        linked=[k for k in kos if k.get('section_id')==u['section_id'] and k.get('source_quote') and k['source_quote'] in u['raw_text'] and k.get('status') not in ['deleted','rejected']]
        hints=[re.sub(r'^\s*(?:[-+*]|\d+[.)])\s+','',x).strip() for x in re.split(r';|\bbut\b|\band\b',u['raw_text']) if x.strip()]
        clauses=[{'text':x,'quote_overlap_ids':[k['id'] for k in linked if x in k['source_quote'] or k['source_quote'] in x]} for x in hints]
        fp=fingerprint([u,linked]);r=saved.get(u['unit_id'])
        out.append(dict(u,linked_ko_ids=[k['id'] for k in linked],clause_hints=hints,clause_candidates=clauses,valid_ko_ids=[k['id'] for k in linked if not k.get('validation_errors')],review=r,review_current=bool(r and r['fingerprint']==fp),fingerprint=fp))
    return out

def review_unit(db,units,kos,p,reviewer):
    row=next((u for u in unit_state(db,units,kos) if u['unit_id']==p.get('unit_id')),None)
    if not row or row['fingerprint']!=p.get('fingerprint'):raise ValueError('Source or KOs changed. Refresh before reviewing coverage.')
    if p.get('decision') not in ['complete','not_a_rule','needs_work']:raise ValueError('Choose a coverage decision.')
    p=dict(p);p['note']=p.get('note','').strip() or 'Coverage decision selected: '+str(p.get('decision'))+'. No free-text explanation supplied.'
    count=p.get('expected_rule_count',0)
    if not isinstance(count,int) or isinstance(count,bool) or count<0:raise ValueError('Enter the number of independent rules you identified.')
    if p['decision']=='complete' and (count<1 or count>len(row['valid_ko_ids'])):raise ValueError('Complete coverage needs a positive reviewer rule count and at least that many valid linked KOs. Add missing KOs first.')
    if p['decision']=='not_a_rule' and count!=0:raise ValueError('A non-rule decision must have zero expected rules.')
    v={k:p[k] for k in ['unit_id','fingerprint','decision','note']};v.update(reviewer=reviewer,time=time.time(),expected_rule_count=count)
    with db:
        db.execute('INSERT OR REPLACE INTO unit_reviews VALUES (?,?)',(p['unit_id'],json.dumps(v)));audit(db,'UNIT:'+p['unit_id'],row['review'],v,reviewer)
    return v

def group_update(db,p,reviewer):
    gid=p.get('group_id','').strip();op=p.get('logical_operator')
    if not gid or op not in ['AND','OR','UNCERTAIN']:raise ValueError('Group ID and operator are required.')
    p=dict(p);p['note']=p.get('note','').strip() or 'Group operator selected: '+op+'. No free-text explanation supplied.'
    rows=[json.loads(r[0]) for r in db.execute('SELECT body FROM state')]
    members=[k for k in rows if k.get('requirement_group_id')==gid and k.get('status') not in ['deleted','rejected']]
    if not members:raise ValueError('No active members in this group.')
    if p.get('fingerprint')!=fingerprint(members):raise ValueError('Group changed. Refresh before applying.')
    with db:
        for old in members:
            new=dict(old,logical_operator=op,requirement_group_note=p['note'],status='proposed',group_reviewed_by=reviewer)
            db.execute('UPDATE state SET body=? WHERE id=?',(json.dumps(new),old['id']));audit(db,old['id'],old,new,reviewer)
    return {'updated':len(members)}

def stage(db,new,existing):
    related=[k for k in existing if k.get('section_id')==new['section_id'] and (set(k.get('source_unit_ids',[]))&set(new.get('source_unit_ids',[])) or k.get('source_quote')==new['source_quote']) and k.get('status')!='deleted']
    if not related:return None
    # Repeated identical proposals do not clutter the comparison queue.
    core={k:v for k,v in new.items() if k not in ['id','run_id','possible_duplicate_of']}
    for r in db.execute('SELECT body FROM rerun_proposals'):
        old=json.loads(r[0])
        if old.get('signature')==fingerprint(core) and old.get('status')=='pending':return old['id']
    v={'id':'DIFF_'+secrets.token_hex(6),'status':'pending','new':new,'existing':related,'signature':fingerprint(core),'time':time.time()}
    db.execute('INSERT INTO rerun_proposals VALUES (?,?)',(v['id'],json.dumps(v)));return v['id']

def comparisons(db):
    init(db);return [json.loads(r[0]) for r in db.execute('SELECT body FROM rerun_proposals ORDER BY rowid DESC')]

def resolve_comparison(db,p,reviewer,validator,sections):
    row=db.execute('SELECT body FROM rerun_proposals WHERE id=?',(p.get('id'),)).fetchone()
    if not row:raise ValueError('Comparison not found.')
    v=json.loads(row[0])
    if v['status']!='pending':raise ValueError('Comparison already resolved.')
    action=p.get('action')
    if action not in ['keep_existing','add_distinct','replace']:raise ValueError('Choose an action.')
    p=dict(p);p['note']=p.get('note','').strip() or 'Rerun decision selected: '+action+'. No free-text explanation supplied.'
    if action!='keep_existing':
        for old in v['existing']:
            current=db.execute('SELECT body FROM state WHERE id=?',(old['id'],)).fetchone()
            if not current or fingerprint(json.loads(current[0]))!=fingerprint(old):raise ValueError('Existing KO changed since extraction. Keep existing and rerun to compare current versions.')
        errors=validator(v['new'],sections)
        if errors:raise ValueError('; '.join(errors))
    ids=p.get('replace_ids',[])
    if action=='replace' and (not ids or not set(ids)<=set(k['id'] for k in v['existing'])):raise ValueError('Select the existing KOs to supersede.')
    oldv=dict(v)
    with db:
        if action!='keep_existing':
            new=dict(v['new'],status='proposed',note=p['note'])
            db.execute('INSERT INTO state VALUES (?,?)',(new['id'],json.dumps(new)));audit(db,new['id'],None,new,reviewer)
            if action=='replace':
                for old in v['existing']:
                    if old['id'] in ids:
                        changed=dict(old,status='rejected',superseded_by=new['id'],note=p['note'])
                        db.execute('UPDATE state SET body=? WHERE id=?',(json.dumps(changed),old['id']));audit(db,old['id'],old,changed,reviewer)
        v.update(status=action,reviewer=reviewer,note=p['note'],reviewed_at=time.time())
        db.execute('UPDATE rerun_proposals SET body=? WHERE id=?',(json.dumps(v),v['id']));audit(db,v['id'],oldv,v,reviewer)
    return v
