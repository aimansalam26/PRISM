"""Cross-project node edits, two-step reversible deletion and explicit restore."""
import json,secrets,sqlite3,time
import scope_grounding
import review_tools
from pathlib import Path
from graph_store import fingerprint

class NodeActions:
 def __init__(self,graph,validator):self.graph=graph;self.validator=validator;self.pending={}
 def locate(self,key):
    project,sep,ident=key.partition('::')
    if not sep or not project or project in ['.','..'] or '/' in project or '\\' in project:raise ValueError('Invalid project key.')
    folder=self.graph.root/project
    if not (folder/'manifest.json').is_file() or not (folder/'annotations.sqlite').is_file():raise ValueError('Project not found.')
    con=sqlite3.connect(folder/'annotations.sqlite');row=con.execute('SELECT body FROM state WHERE id=?',(ident,)).fetchone()
    if not row:con.close();raise ValueError('KO not found.')
    sections=json.loads((folder/'parsed_sections.json').read_text(encoding='utf-8'))
    return con,json.loads(row[0]),{s['section_id']:s for s in sections}
 def write(self,con,old,new,reviewer):
    with con:
        con.execute('CREATE TABLE IF NOT EXISTS audit (time REAL,reviewer TEXT,id TEXT,before TEXT,after TEXT)')
        con.execute('UPDATE state SET body=? WHERE id=?',(json.dumps(new),old['id']))
        con.execute('INSERT INTO audit VALUES (?,?,?,?,?)',(time.time(),reviewer,old['id'],json.dumps(old),json.dumps(new)))
 def context(self,key):
    con,k,sections=self.locate(key)
    try:
        section=sections.get(k.get('section_id'),{})
        return {'key':key,'ko':k,'fingerprint':fingerprint(k),'context_options':review_tools.context_options(section,list(sections.values())), 'scope_report':scope_grounding.report(k,sections)}
    finally:con.close()
 def edit(self,p,reviewer):
    con,old,sections=self.locate(p['key'])
    try:
        if old.get('status')=='deleted':raise ValueError('Restore this KO before editing.')
        if p.get('fingerprint')!=fingerprint(old):raise ValueError('KO changed in another view. Refresh before saving.')
        new=dict(old)
        for field in ['summary','source_quote','watched_fields','applicability_tuples','scope_evidence','additional_conditions','note','context_evidence','scope_support']: 
            if field in p:new[field]=p[field]
        new=scope_grounding.reconcile(new,sections)
        new['scope_readiness']=scope_grounding.scope_readiness(new,sections)
        new['status']='proposed' # semantic edits invalidate prior approval
        if p.get('decision') not in [None,'proposed','approved']:raise ValueError('Invalid review decision.')
        errors=self.validator(new,sections)
        if errors:raise ValueError('; '.join(errors))
        if p.get('decision')=='approved':
            unsupported=[r for r in scope_grounding.report(new,sections) if r['status']=='unsupported']
            if unsupported:raise ValueError('; '.join(r['dimension']+'='+r['value']+': '+r['reason'] for r in unsupported))
            new['status']='approved'
            new['curation_review']={'reviewer':reviewer,'decision':'approved','time':time.time(),'origin':'candidate_review'}
        new['validation_errors']=[];new['edited_by']=reviewer;new['edited_at']=time.time()
        self.write(con,old,new,reviewer);return new
    finally:con.close()
 def incident(self,key):
    return [json.loads(r[0]) for r in self.graph.db.execute('SELECT body FROM edges') if key in [json.loads(r[0])['source'],json.loads(r[0])['target']]]
 def prepare_delete(self,key):
    con,k,_=self.locate(key);con.close()
    if k.get('status')=='deleted':raise ValueError('Already in trash.')
    incident=self.incident(key);nonce=secrets.token_urlsafe(24)
    self.pending={n:v for n,v in self.pending.items() if v['expires']>time.time()}
    self.pending[nonce]={'key':key,'fingerprint':fingerprint(k),'edges':fingerprint(incident),'expires':time.time()+180}
    return {'confirmation_token':nonce,'key':key,'id':k['id'],'summary':k['summary'],'connected_edges':len(incident),'message':'Move this node to trash? It will disappear from active graphs. Connected edges remain in the audit and become stale. Restore is available.'}
 def delete(self,p,reviewer):
    challenge=self.pending.pop(p.get('confirmation_token'),None)
    if not challenge or challenge['expires']<time.time():raise ValueError('Confirmation expired. Start deletion again.')
    con,k,_=self.locate(challenge['key'])
    try:
        if p.get('typed_id')!=k['id']:raise ValueError('KO ID does not match. Nothing deleted.')
        if fingerprint(k)!=challenge['fingerprint'] or fingerprint(self.incident(challenge['key']))!=challenge['edges']:raise ValueError('Node or connections changed. Refresh and review deletion again.')
        new=dict(k);new.update(status='deleted',deletion={'previous_status':k.get('status'),'reviewer':reviewer,'time':time.time()})
        self.write(con,k,new,reviewer);return {'deleted':challenge['key'],'recoverable':True}
    finally:con.close()
 def restore(self,key,reviewer):
    con,k,_=self.locate(key)
    try:
        if k.get('status')!='deleted':raise ValueError('Node is not in trash.')
        new=dict(k);new.update(status='proposed',restored_by=reviewer,restored_at=time.time())
        self.write(con,k,new,reviewer);return {'restored':key,'status':'proposed'}
    finally:con.close()
