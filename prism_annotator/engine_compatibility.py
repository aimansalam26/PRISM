"""Read-only handoff checks for PRISM engine 0.3.0 and handbook schema 0.4."""
import json
import scope_grounding

def report(graph):
    state=graph.state();issues=[];cache={}
    def add(key,code,message):issues.append({'record':key,'code':code,'message':message})
    for n in state['nodes']:
        k=n['ko']
        if k.get('status') in ['deleted','rejected']:continue
        if n['project'] not in cache:cache[n['project']]={s['section_id']:s for s in json.loads((graph.root/n['project']/'parsed_sections.json').read_text(encoding='utf-8'))}
        if k.get('status')!='approved':add(n['key'],'curation_pending','Curate this KO before final verification.')
        unresolved=[r for r in scope_grounding.report(k,cache[n['project']]) if r['status']!='source_supported']
        if unresolved:add(n['key'],'scope_unresolved','Unknown scope will cause Defer where overlap remains possible; unsupported claims must be corrected before verification.')
    for e in state['edges']:
        if e.get('status')=='rejected':continue
        if e.get('effective_status')!='approved':add(e['id'],'edge_review','Review this connection and its current endpoints.')
        if e.get('certainty','uncertain')!='confirmed':add(e['id'],'uncertain_relation','Connection will produce Defer on temporally possible paths.')
        if not e.get('applicability_tuples'):add(e['id'],'unknown_edge_scope','Connection scope is not recorded; converter will retain it as unknown, not universal.')
        if e['relation_type'] in ['REVIEW_ONLY','OVERRIDES'] and not e.get('trigger_fields'):add(e['id'],'trigger_fields_missing','Select source trigger fields in Graph review.')
        if e['relation_type']=='OVERRIDES' and e.get('override_mode')!='independent_value':add(e['id'],'override_mode','Review whether this is an independent fixed-value replacement.')
    return {'engine_ready':False,'target_engine':'PRISM 0.3.0 / schema 0.4','issues':issues,'required_adapter_work':['Finally verify the KOs and connections, then download the verification packet.','Use prism build-scenario (menu 9) to supply an explicit before/after change event.','Unknown applicability remains null and produces possible impacts (Defer), never definite scope.','Start is inclusive and end exclusive. Do not use commit timestamps as applicability dates.'],'engine_limitations':['Traversal remains bounded to 1–3 hops. Scope withdrawals and relationship changes are not supported.','Requirement groups are preserved as provenance; this engine discovers review impact, not employee benefit eligibility.','Only finally verified records are imported; omitted records are listed in the scenario.'],'warnings':state['warnings']}
