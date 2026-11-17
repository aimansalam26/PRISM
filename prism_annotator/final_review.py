"""Version-bound, low-typing final verification, separate from curation approval."""
import json,time
from graph_store import fingerprint
import scope_grounding as scope

def init(graph):
    graph.db.execute('CREATE TABLE IF NOT EXISTS final_reviews(id TEXT PRIMARY KEY,body TEXT)');graph.db.commit()

def packet(graph,validator):
    init(graph);s=graph.state();saved={r[0]:json.loads(r[1]) for r in graph.db.execute('SELECT id,body FROM final_reviews')};items=[];contexts={}
    for n in s['nodes']:
        if n['ko'].get('status')!='approved':continue
        if n['project'] not in contexts:
            contexts[n['project']]={x['section_id']:x for x in json.loads((graph.root/n['project']/'parsed_sections.json').read_text(encoding='utf-8'))}
        sections=contexts[n['project']];k=n['ko'];scope_rows=scope.report(k,sections);errors=validator(k,sections)
        if any(r['status']=='unsupported' for r in scope_rows):errors.append('One or more claimed applicability values have no supported source citation. Return to curator.')
        items.append({'id':'ko:'+n['key'],'kind':'ko','key':n['key'],'summary':k['summary'],'quote':k['source_quote'],'heading_path':n['section'].get('heading_path',[]),'source_file':n['source_file'],'line':n['quote_line_start'],'context_evidence':k.get('context_evidence',[]),'scope':scope_rows,'scope_readiness':scope.scope_readiness(k,sections),'conditions':k.get('additional_conditions',[]),'group':{'id':k.get('requirement_group_id'),'operator':k.get('logical_operator','UNCERTAIN')},'errors':errors,'fingerprint':fingerprint([n['fingerprint'],n['source_sha256']])})
    bykey={x['key']:x for x in items}
    for e in s['edges']:
        if e.get('status')!='approved':continue
        errors=list(e.get('stale_reasons',[]))
        if any(end not in bykey for end in [e['source'],e['target']]):errors.append('Both KOs must be curated first.')
        # Final edge decisions depend on current endpoint content as well as edge content.
        fp=fingerprint([e,[(x,bykey.get(x,{}).get('fingerprint')) for x in [e['source'],e['target']]]])
        items.append({'id':'edge:'+e['id'],'kind':'edge','summary':e['relation_type'],'source':e['source'],'target':e['target'],'source_summary':bykey.get(e['source'],{}).get('summary',e['source']),'target_summary':bykey.get(e['target'],{}).get('summary',e['target']),'evidence':e['evidence'],'justification':e['justification'],'scope_notes':e.get('scope_notes',''),'field_mappings':e['field_mappings'],'dimension_mapping':e['dimension_mapping'],'errors':errors,'fingerprint':fp})
    for item in items:
        r=saved.get(item['id']);item['review']=r;item['current']=bool(r and r['fingerprint']==item['fingerprint'] and not item['errors']);item['decision']=r['decision'] if item['current'] else 'pending'
    # Edge verification must stay invalid if either final endpoint decision is withdrawn.
    node_decisions={x['key']:x['decision'] for x in items if x['kind']=='ko'}
    for x in items:
        if x['kind']=='edge' and any(node_decisions.get(k)!='accept' for k in [x['source'],x['target']]):
            x['errors'].append('Verify both endpoint KOs first.');x['current']=False;x['decision']='pending'
    return {'items':items,'warnings':s['warnings'],'engine_ready':False,'notice':'Annotation export only: engine admission must check unresolved scope and edge semantics. Verify source meaning and applicability. Unknown is not universal. This review does not execute scope traversal.','counts':{'total':len(items),'accepted':sum(x['decision']=='accept' for x in items),'pending':sum(x['decision']=='pending' for x in items)}}

def decide(graph,p,reviewer,validator):
    item=next((x for x in packet(graph,validator)['items'] if x['id']==p.get('id')),None)
    if not item or item['fingerprint']!=p.get('fingerprint'):raise ValueError('Item changed. Refresh and inspect the current evidence.')
    action=p.get('decision')
    if action not in ['accept','needs_fix','reject']:raise ValueError('Choose a decision.')
    if action=='accept':
        if p.get('evidence_checked') is not True:raise ValueError('Confirm that you checked the displayed source evidence.')
        if item['errors']:raise ValueError('; '.join(item['errors']))
    reason=p.get('reason','')
    if reason not in ['matches_source','unclear_meaning','unsupported_scope','missing_condition','wrong_connection','not_a_rule','other']:raise ValueError('Choose a reason from the list.')
    if action=='accept' and reason!='matches_source':raise ValueError('Acceptance requires the matches-source reason.')
    if action!='accept' and reason=='matches_source':raise ValueError('Choose a correction/rejection reason.')
    value={'id':item['id'],'fingerprint':item['fingerprint'],'decision':action,'reason_code':reason,'comment':str(p.get('comment','')),'reviewer':reviewer,'time':time.time(),'evidence_checked':p.get('evidence_checked') is True,'origin':'human_click'}
    old=graph.db.execute('SELECT body FROM final_reviews WHERE id=?',(item['id'],)).fetchone()
    with graph.db:
        graph.db.execute('INSERT OR REPLACE INTO final_reviews VALUES (?,?)',(item['id'],json.dumps(value)))
        graph.db.execute('INSERT INTO audit VALUES (?,?,?,?,?)',(time.time(),reviewer,'FINAL:'+item['id'],old[0] if old else None,json.dumps(value)))
    return value
