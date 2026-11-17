"""Read-only compatibility audit against the supplied PRISM 0.2.0 engine.
Never fabricates schema 0.3 input or converts missing values to wildcards.
"""
import scope_grounding
import json

def report(graph):
    state=graph.state();issues=[];cache={}
    def add(key,code,message):issues.append({'record':key,'code':code,'message':message})
    for n in state['nodes']:
        k=n['ko']
        if k.get('status') in ['deleted','rejected']:continue
        if n['project'] not in cache:
            cache[n['project']]={s['section_id']:s for s in json.loads((graph.root/n['project']/'parsed_sections.json').read_text(encoding='utf-8'))}
        if k.get('status')!='approved':add(n['key'],'curation_pending','KO has not been approved.')
        for r in scope_grounding.report(k,cache[n['project']]):
            if r['status']!='source_supported':add(n['key'],'scope_'+r['status'],f"Tuple {r['tuple_index']+1}: {r['dimension']} = {r['value']}.")
        if k.get('requirement_group_id'):add(n['key'],'group_semantics','Engine does not evaluate requirement_group AND/OR expressions.')
    for e in state['edges']:
        if e.get('status')=='rejected':continue
        if e.get('effective_status')!='approved':add(e['id'],'edge_review','Connection is proposed, stale or needs correction.')
        if e['relation_type']=='CALCULATES_VALUE':add(e['id'],'unsupported_relation','Engine TYPES does not include CALCULATES_VALUE. Requires an explicit engine/adapter decision.')
        if any(m['source_field']!=m['target_field'] for m in e.get('field_mappings',[])):add(e['id'],'field_transfer','Engine carries one unchanged field along a path; source-to-target field renaming is not implemented.')
        add(e['id'],'edge_scope','Engine requires explicit scope cells and confirmed/uncertain certainty on every relationship; annotation scope_notes are not those fields.')
        if e['relation_type'] in ['REVIEW_ONLY','OVERRIDES']:add(e['id'],'watched_field','Engine requires a watched field for this relation even though it does not propagate a mapped output field.')
        if e['relation_type']=='OVERRIDES':add(e['id'],'override_mode','Engine supports independent_value overrides only; this must be evidenced, not assumed.')
    return {'engine_ready':False,'target_engine':'PRISM 0.2.0 / schema 0.3','issues':issues,'required_adapter_work':[
        'Map employment_types and org_roles to engine roles without flattening an AND condition into alternatives.',
        'Map entities to organisations and preserve each correlated tuple as a separate scope cell.',
        'Provide evidenced ISO temporal bounds; engine uses start-inclusive/end-exclusive intervals. Unknown is not a wildcard or a date.',
        'Supply a before/after change event, changed fields and root version; annotation export alone is not a scenario.',
        'Require current final verification and valid connection evidence before engine admission.'
    ],'engine_limitations':['Gold workbook reader currently filters KO IDs by an S prefix; empirical KO_ IDs need an evaluator update.', 'Maximum 3 hops. Scope withdrawals and relationship changes are rejected.','Population values unknown/unspecified are currently treated as literal labels by the supplied engine: do not send them.','Uncertain REVIEW_ONLY currently continues as Defer in the supplied engine; this differs from the intended terminal rule.'], 'warnings':state['warnings']}
