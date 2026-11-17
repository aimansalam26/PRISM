"""Shared, human-annotated graph across sibling Markdown projects."""
import hashlib,json,secrets,sqlite3,time
from pathlib import Path
from datetime import date
from copy import deepcopy
import scope_grounding
TYPES=['DEPENDS_ON','CALCULATES_VALUE','ADOPTS_VALUE','REVIEW_ONLY','OVERRIDES','RELATED_TO']
DIMENSIONS=['employment_types','org_roles','entities','jurisdictions','temporal_window']

def fingerprint(k):
    return hashlib.sha256(json.dumps(k,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def unknown_scope():return {**{d:['unknown'] for d in DIMENSIONS[:-1]},'temporal_window':['unknown','unknown']}
def validate_edge_scope(tuples):
    if not isinstance(tuples,list) or not 1<=len(tuples)<=4:raise ValueError('Use one to four edge applicability cases.')
    for t in tuples:
        if not isinstance(t,dict) or set(t)!=set(DIMENSIONS):raise ValueError('Edge applicability needs all five dimensions.')
        for d in DIMENSIONS:
            if not isinstance(t[d],list) or not t[d] or any(not isinstance(v,str) or not v.strip() for v in t[d]):raise ValueError('Invalid edge scope '+d)
            if any(v in ['*','all'] for v in t[d]):raise ValueError('Do not use unproven wildcard scope; use unknown.')
        if len(t['temporal_window'])!=2:raise ValueError('Edge temporal window needs two endpoints.')
        bounds=t['temporal_window']
        for v in bounds:
            if v not in ['unknown','unspecified']:
                try:
                    if date.fromisoformat(v).isoformat()!=v:raise ValueError()
                except ValueError:raise ValueError('Use ISO dates or unknown for edge effective dates.') from None
        if all(v not in ['unknown','unspecified'] for v in bounds) and bounds[0]>=bounds[1]:raise ValueError('Edge effective start must precede exclusive end.')

class GraphStore:
 def __init__(self,root):
    self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
    self.db=sqlite3.connect(self.root/'prism_graph.sqlite')
    self.db.execute('CREATE TABLE IF NOT EXISTS edges (id TEXT PRIMARY KEY,body TEXT)')
    self.db.execute('CREATE TABLE IF NOT EXISTS audit (time REAL,reviewer TEXT,id TEXT,before TEXT,after TEXT)')
    self.db.execute('CREATE TABLE IF NOT EXISTS positions (id TEXT PRIMARY KEY,x REAL,y REAL)')
 def nodes(self,include_deleted=False):
    nodes=[];warnings=[];projects=[]
    for p in sorted(self.root.glob('*/manifest.json')):
     folder=p.parent
     if not (folder/'annotations.sqlite').exists():continue
     try:
      manifest=json.loads(p.read_text(encoding='utf-8'))
      ss={s['section_id']:s for s in json.loads((folder/'parsed_sections.json').read_text(encoding='utf-8'))}
      con=sqlite3.connect((folder/'annotations.sqlite').as_uri()+'?mode=ro',uri=True)
      try:rows=con.execute('SELECT body FROM state').fetchall()
      finally:con.close()
      projects.append({'id':folder.name,'source_file':manifest['source_file'],'count':len(rows)})
      for row in rows:
       k=json.loads(row[0])
       if k.get('status')=='deleted' and not include_deleted:continue
       key=folder.name+'::'+k['id'];s=ss.get(k.get('section_id'),{})
       quote=k.get('source_quote','');raw=s.get('raw_text','');pos=raw.find(quote) if quote else -1
       errors=list(k.get('validation_errors',[]))
       if pos<0:errors.append('Quote does not match saved section.')
       line=s.get('line_start',1)+raw[:max(pos,0)].count('\n')
       nodes.append({'key':key,'project':folder.name,'ko':k,'fingerprint':fingerprint(k),'source_file':manifest['source_file'],'source_sha256':manifest['source_sha256'],'section':s,'quote_line_start':line if pos>=0 else None,'errors':errors})
     except (OSError,ValueError,sqlite3.Error,KeyError) as e:warnings.append(folder.name+': '+str(e))
    return nodes,projects,warnings
 def state(self):
    nodes,projects,warnings=self.nodes();lookup={n['key']:n for n in nodes};edges=[]
    for row in self.db.execute('SELECT body FROM edges ORDER BY rowid'):
     e=json.loads(row[0]);issues=[]
     for end in ['source','target']:
      n=lookup.get(e[end])
      if not n:issues.append(end+' node missing')
      elif n['fingerprint']!=e['endpoint_versions'][end]:issues.append(end+' KO changed since this edge was reviewed')
     e['stale']=bool(issues);e['stale_reasons']=issues
     e['effective_status']='needs_correction' if issues and e['status']!='rejected' else e['status']
     e['scope_incomplete']=any('unknown' in json.dumps(lookup.get(e[x],{}).get('ko',{}).get('applicability_tuples',[])).lower() or 'unspecified' in json.dumps(lookup.get(e[x],{}).get('ko',{}).get('applicability_tuples',[])).lower() for x in ['source','target'])
     edges.append(e)
    trash=[n for n in self.nodes(include_deleted=True)[0] if n['ko'].get('status')=='deleted']
    return {'nodes':nodes,'trash':trash,'edges':edges,'projects':projects,'warnings':warnings,'types':TYPES,'positions':{r[0]:{'x':r[1],'y':r[2]} for r in self.db.execute('SELECT * FROM positions')},'workspace':str(self.root),'scope_notice':'Edge approval verifies annotation only; applicability and transfer semantics are not executed here.'}
 def save_edge(self,p,reviewer):
    nodes,_,_=self.nodes();lookup={n['key']:n for n in nodes}
    a=p.get('source');b=p.get('target');typ=p.get('relation_type');status=p.get('status','proposed')
    if a not in lookup or b not in lookup:raise ValueError('Choose two existing nodes.')
    if a==b:raise ValueError('Self-links are not supported.')
    if typ not in TYPES:raise ValueError('Unknown relationship type.')
    if status not in ['proposed','approved','needs_correction','rejected']:raise ValueError('Invalid status.')
    note=p.get('justification','').strip()
    if not note:raise ValueError('Explain why this relationship is supported.')
    mappings=p.get('field_mappings',[])
    if not isinstance(mappings,list):raise ValueError('Field mappings must be a list.')
    for m in mappings:
     if not isinstance(m,dict) or m.get('source_field') not in lookup[a]['ko']['watched_fields'] or m.get('target_field') not in lookup[b]['ko']['watched_fields']:raise ValueError('Mappings must name existing source and target watched fields.')
    propagative=typ in ['DEPENDS_ON','CALCULATES_VALUE','ADOPTS_VALUE']
    if propagative and not mappings:raise ValueError('Propagative edges require at least one field mapping.')
    if not propagative and mappings:raise ValueError('Terminal, blocked and topical links must have no propagated field mappings.')
    rewrite=deepcopy(p.get('dimension_mapping',[]))
    if not isinstance(rewrite,list):raise ValueError('Dimension mapping must be a list.')
    if typ=='ADOPTS_VALUE':
     if not rewrite:raise ValueError('ADOPTS_VALUE requires an explicit dimension mapping.')
     for m in rewrite:
      if not isinstance(m,dict) or m.get('dimension') not in DIMENSIONS[:-1] or not isinstance(m.get('from'),list) or not m['from'] or not isinstance(m.get('to'),list) or not m['to']:raise ValueError('Adoption needs a population dimension and from/to lists; dates cannot be rewritten.')
      if any(not isinstance(v,str) or not v.strip() or v.strip().lower() in ['unknown','unspecified','*'] for v in m['from']+m['to']):raise ValueError('Adoption mappings need explicit known population values.')
      for side in ['from','to']:m[side]=[scope_grounding.canonical_value(m['dimension'],v) for v in m[side]]
    elif rewrite:raise ValueError('Dimension rewriting is only for ADOPTS_VALUE.')
    if status=='approved':
     if any(lookup[x]['ko'].get('status')!='approved' or lookup[x]['errors'] for x in [a,b]):raise ValueError('Approve and validate both KOs before approving an edge. You can save a proposal now.')
    certainty=p.get('certainty','uncertain')
    if certainty not in ['confirmed','uncertain']:raise ValueError('Choose confirmed or uncertain relation certainty.')
    uncertainty=str(p.get('uncertainty_reason','')).strip()
    if certainty=='uncertain' and not uncertainty:uncertainty='Relationship certainty has not been explicitly confirmed.'
    triggers=p.get('trigger_fields',[])
    if not isinstance(triggers,list) or any(f not in lookup[a]['ko']['watched_fields'] for f in triggers):raise ValueError('Trigger fields must belong to the source KO.')
    if status=='approved' and typ in ['REVIEW_ONLY','OVERRIDES'] and not triggers:raise ValueError('Select the source field(s) that trigger this terminal/blocked connection.')
    scope=deepcopy(p.get('applicability_tuples') or [unknown_scope()]);validate_edge_scope(scope)
    for t in scope:
     for dim in DIMENSIONS:
      t[dim]=[scope_grounding.canonical_value(dim,v) for v in t[dim]]
      if any(scope_grounding.dimension_problem(dim,v) for v in t[dim]):raise ValueError('Wrong scope dimension: '+dim)
    if any(v not in ['unknown','unspecified'] for t in scope for values in t.values() for v in values) and not str(p.get('scope_notes','')).strip():raise ValueError('Explain the source evidence for known edge scope in Scope restrictions / uncertainties.')
    override=p.get('override_mode','')
    if typ=='OVERRIDES' and status=='approved' and override!='independent_value':raise ValueError('Only an evidenced independent-value override is supported by the engine.')
    ident=p.get('id') or 'EDGE_'+secrets.token_hex(6)
    for row in self.db.execute('SELECT body FROM edges'):
     old=json.loads(row[0])
     if old['id']!=ident and old['source']==a and old['target']==b and old['relation_type']==typ and old['status']!='rejected' and status!='rejected':raise ValueError('This directed relationship already exists. Select its edge to edit it.')
    e={k:p.get(k) for k in ['source','target','relation_type']}
    if p.get('ai_proposal_id'):e['origin_proposal_id']=p['ai_proposal_id']
    e.update(certainty=certainty,uncertainty_reason=uncertainty,trigger_fields=list(dict.fromkeys(triggers)),applicability_tuples=scope,override_mode=override,id=ident,status=status,justification=note,field_mappings=mappings,dimension_mapping=rewrite,scope_notes=str(p.get('scope_notes','')),endpoint_versions={x:lookup[e[x]]['fingerprint'] for x in ['source','target']},reviewer=reviewer,updated_at=time.time(),evidence=[{'node':x,'quote':lookup[x]['ko']['source_quote'],'source_file':lookup[x]['source_file'],'source_sha256':lookup[x]['source_sha256'],'section_id':lookup[x]['ko']['section_id'],'line_start':lookup[x]['quote_line_start']} for x in [a,b]])
    old=self.db.execute('SELECT body FROM edges WHERE id=?',(ident,)).fetchone()
    with self.db:
     self.db.execute('INSERT OR REPLACE INTO edges VALUES (?,?)',(ident,json.dumps(e)))
     self.db.execute('INSERT INTO audit VALUES (?,?,?,?,?)',(time.time(),reviewer,ident,old[0] if old else None,json.dumps(e)))
    return e
 def save_position(self,p):
    x=float(p['x']);y=float(p['y'])
    if not (-100000<=x<=100000 and -100000<=y<=100000):raise ValueError('Position outside canvas bounds.')
    with self.db:self.db.execute('INSERT OR REPLACE INTO positions VALUES (?,?,?)',(str(p['key']),x,y))
    return {'saved':True}
 def save_layout(self,positions):
    if not isinstance(positions,list) or len(positions)>10000:raise ValueError('Invalid layout.')
    allowed={n['key'] for n in self.nodes()[0]};rows=[]
    for p in positions:
     x=float(p['x']);y=float(p['y']);key=str(p['key'])
     if key not in allowed or not (-100000<=x<=100000 and -100000<=y<=100000):raise ValueError('Invalid node or coordinates; no layout changes saved.')
     rows.append((key,x,y))
    with self.db:self.db.executemany('INSERT OR REPLACE INTO positions VALUES (?,?,?)',rows)
    return {'saved':len(rows)}
 def export(self):
    s=self.state();s['engine_ready']=False;s['export_purpose']='annotation_review';s['engine_contract']='Never treat unknown or unspecified as universal or as empty. Approval alone does not establish scope completeness. Engine adapter must resolve or defer uncertainty and validate final reviews, relation semantics and field mappings.';s['approved_edges']=[e for e in s['edges'] if e['effective_status']=='approved'];s['audit']=[dict(zip(['time','reviewer','id','before','after'],r)) for r in self.db.execute('SELECT * FROM audit')];return s
