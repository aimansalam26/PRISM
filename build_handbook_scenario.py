"""Convert a current final-verification packet and an explicit change event.
No model calls, inferred effective dates, synthetic dependencies or wildcard filling.
"""
import argparse,copy,hashlib,json
from datetime import date,timedelta
from pathlib import Path
from engine import validate,HANDBOOK_DIMENSIONS
UNKNOWN={'unknown','unspecified','not stated',''}

def annotation_hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def unknown_cell():return {**{d:None for d in HANDBOOK_DIMENSIONS},'start':None,'end':None}

def scope_cell(t,end_convention=None):
    c={}
    for d in HANDBOOK_DIMENSIONS:
        values=t.get(d)
        if not isinstance(values,list) or not values:raise ValueError('Missing annotation scope dimension '+d)
        if any(not isinstance(v,str) for v in values):raise ValueError('Scope values must be strings.')
        c[d]=None if any(v.strip().lower() in UNKNOWN for v in values) else list(dict.fromkeys(values))
        if c[d] and '*' in c[d]:raise ValueError('Annotation wildcards need an explicit evidenced policy; this importer does not infer or admit them.')
    bounds=t.get('temporal_window')
    if not isinstance(bounds,list) or len(bounds)!=2:raise ValueError('Temporal window needs two endpoints.')
    for key,value in zip(['start','end'],bounds):c[key]=None if value is None or str(value).strip().lower() in UNKNOWN else value
    if c['end'] is not None:
        if end_convention not in ['inclusive','exclusive']:raise ValueError('Known end dates require explicit end_date_convention: inclusive or exclusive (global or per record).')
        if end_convention=='inclusive':
            try:c['end']=(date.fromisoformat(c['end'])+timedelta(days=1)).isoformat()
            except (ValueError,OverflowError):raise ValueError('Cannot convert inclusive end date to exclusive bound.') from None
    return c

def reviewed_graph(packet):
    if not isinstance(packet,dict) or not isinstance(packet.get('graph'),dict) or not isinstance(packet.get('items'),list):raise ValueError('Use Download verification packet in Final verification, not a raw graph export.')
    graph=packet['graph'];items={i['id']:i for i in packet['items']}
    def accepted(i):return i and i.get('current') is True and i.get('decision')=='accept' and not i.get('errors') and i.get('review',{}).get('fingerprint')==i.get('fingerprint')
    nodes=[];edges=[];omitted=[]
    for n in graph['nodes']:
        item=items.get('ko:'+n['key'])
        if not accepted(item):omitted.append(n['key']);continue
        fp=annotation_hash(n['ko'])
        if n.get('fingerprint')!=fp or item['fingerprint']!=annotation_hash([fp,n['source_sha256']]):raise ValueError('KO changed after verification: '+n['key'])
        if n['ko'].get('status')!='approved' or n.get('errors'):raise ValueError('KO is not currently approved: '+n['key'])
        quote=n['ko'].get('source_quote','')
        if not quote or quote not in n.get('section',{}).get('raw_text',''):raise ValueError('KO quote does not match saved source: '+n['key'])
        if any(r.get('status')=='unsupported' for r in item.get('scope',[])):raise ValueError('Unsupported scope claim: '+n['key'])
        nodes.append(n)
    bykey={n['key']:n for n in nodes}
    for e in graph['edges']:
        item=items.get('edge:'+e['id'])
        if not accepted(item):omitted.append(e['id']);continue
        if e.get('effective_status')!='approved' or e.get('stale') or any(x not in bykey for x in [e['source'],e['target']]):raise ValueError('Connection needs current endpoint verification: '+e['id'])
        fp=annotation_hash([e,[(k,items['ko:'+k]['fingerprint']) for k in [e['source'],e['target']]]])
        if item['fingerprint']!=fp:raise ValueError('Connection changed after verification: '+e['id'])
        edges.append(e)
    return nodes,edges,omitted

def build(packet,change):
    annotations,connections,omitted=reviewed_graph(packet);lookup={n['key']:n for n in annotations}
    root=change.get('root_ko')
    if root not in lookup:raise ValueError('Select a currently finally verified root KO.')
    def convention(key):
        declared=change.get('end_date_convention')
        return declared.get(key) if isinstance(declared,dict) else declared
    nodes=[]
    for n in annotations:
        k=n['ko'];nodes.append({'id':n['key'],'title':k['summary'],'text':k['source_quote'],'scope_cells':[scope_cell(t,convention(n['key'])) for t in k['applicability_tuples']],'watched_fields':k['watched_fields'],'source':{'file':n['source_file'],'sha256':n['source_sha256'],'section_id':k['section_id'],'line':n.get('quote_line_start'),'annotation_fingerprint':n['fingerprint']},'requirement_group':{'id':k.get('requirement_group_id'),'operator':k.get('logical_operator','UNCERTAIN')}})
    relationships=[]
    for e in connections:
        rel={'id':e['id'],'prerequisite':e['source'],'dependent':e['target'],'type':e['relation_type'],'field_mappings':e.get('field_mappings',[]),'trigger_fields':e.get('trigger_fields',[]),'scope_cells':[scope_cell(t,convention(e['id'])) for t in e['applicability_tuples']] if e.get('applicability_tuples') else [unknown_cell()],'certainty':e.get('certainty','uncertain'),'source':e['evidence'],'evidence':e['justification']}
        if rel['certainty']=='uncertain':rel['uncertainty_reason']=e.get('uncertainty_reason') or 'Relationship certainty has not been explicitly confirmed.'
        if rel['type']=='OVERRIDES':
            if e.get('override_mode')!='independent_value':raise ValueError(e['id']+': confirm independent-value override semantics in Graph review before exporting.')
            rel['override_mode']='independent_value'
        if rel['type']=='ADOPTS_VALUE':
            rel['mapping']={'from':{},'to':{}}
            for m in e['dimension_mapping']:
                if m['dimension'] in rel['mapping']['from']:raise ValueError('Duplicate adoption dimension on '+e['id'])
                rel['mapping']['from'][m['dimension']]=m['from'];rel['mapping']['to'][m['dimension']]=m['to']
        if rel['type'] not in ['RELATED_TO','DEPENDS_ON','CALCULATES_VALUE','ADOPTS_VALUE'] and not rel['trigger_fields']:raise ValueError(e['id']+': choose watched trigger fields in Graph review for this terminal/blocked link.')
        relationships.append(rel)
    root_node=next(n for n in nodes if n['id']==root);before=copy.deepcopy(change.get('before',{}))
    if not before.get('text') or not before.get('source') or before['text']==root_node['text']:raise ValueError('Provide different before-text and its source evidence. The root KO supplies the after-text.')
    fields=change.get('changed_fields',[])
    if any(f not in root_node['watched_fields'] for f in fields):raise ValueError('Changed fields must belong to the root KO.')
    if not isinstance(change.get('id'),str) or not change['id'].strip():raise ValueError('Provide a change-event id.')
    if not before.get('version_id'):raise ValueError('Provide the before version identifier.')
    if 'scope' not in before and 'scope_cells' not in before:
        if change.get('analysis_basis')!='revised_clause_only':raise ValueError('Unknown prior applicability requires explicit revised_clause_only analysis.')
        before.update(scope_cells=[unknown_cell()],scope_known=False)
    event={'kind':change.get('kind','value_change'),'root_ko':root,'changed_fields':fields,'before':before,'after':{'version_id':root,'text':root_node['text'],'scope_cells':copy.deepcopy(root_node['scope_cells']),'source':root_node['source']},'analysis_basis':change.get('analysis_basis','')}
    if 'change_scope' in change:event['change_scope']=change['change_scope']
    else:
        idx=change.get('change_scope_case',0)
        if type(idx) is not int or not 0<=idx<len(root_node['scope_cells']):raise ValueError('Invalid zero-based change_scope_case.')
        if len(root_node['scope_cells'])>1 and 'change_scope_case' not in change:raise ValueError('Select a change_scope_case explicitly for a multi-case root.')
        event['change_scope']=copy.deepcopy(root_node['scope_cells'][idx])
    for key in ['scope_change','relationship_changes']:
        if key in change:event[key]=change[key]
    scenario={'schema_version':'0.4','id':change['id'],'snapshot_id':change['id'],'title':change.get('title') or root_node['title'],'event':event,'nodes':nodes,'relationships':relationships,'annotation_import':{'omitted_unverified_records':omitted,'unknown_policy':'Defer possible paths; prune only established contradictions.','date_semantics':'start inclusive; end exclusive. No dates inferred from commits.','source_packet_sha256':annotation_hash(packet),'end_date_convention':change.get('end_date_convention'),'original_node_scopes':{n['key']:n['ko']['applicability_tuples'] for n in annotations},'original_edge_scopes':{e['id']:e.get('applicability_tuples') for e in connections}}}
    # Scope IDs to the event so the same reviewed graph can appear in a multi-event suite.
    remap={n['id']:change['id']+'::'+n['id'] for n in nodes}
    for n in nodes:n['annotation_key']=n['id'];n['id']=remap[n['id']]
    for e in relationships:e['prerequisite']=remap[e['prerequisite']];e['dependent']=remap[e['dependent']]
    event['root_ko']=remap[root];event['after']['version_id']=remap[root]
    validate(scenario)
    return scenario

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--annotations',type=Path);p.add_argument('--event',type=Path);p.add_argument('--output',type=Path,default=Path('data/handbook_scenario.json'));args=p.parse_args()
    try:
        path=args.annotations or Path(input('Final verification packet JSON path: ').strip().strip('"'));packet=json.loads(path.read_text(encoding='utf-8-sig'))
        if args.event:change=json.loads(args.event.read_text(encoding='utf-8-sig'))
        else:
            ns,es,omitted=reviewed_graph(packet)
            if not ns:raise ValueError('No currently finally verified KOs in this packet.')
            for i,n in enumerate(ns,1):print(f"[{i}] {n['ko']['summary']} ({n['key']})")
            choice=int(input('Changed KO number: '))
            if not 1<=choice<=len(ns):raise ValueError('Choose a displayed KO number.')
            n=ns[choice-1];fields=n['ko']['watched_fields'];print('Available fields:',', '.join(fields));changed=[x.strip() for x in input('Changed field(s), comma-separated: ').split(',')]
            source=Path(input('Before-version Markdown file path: ').strip().strip('"'));raw=source.read_bytes();text=input('Exact previous rule quote (one line; use --event JSON for multiline): ')
            if not text or text not in raw.decode('utf-8-sig'):raise ValueError('Before quote is not an exact substring of the selected source file.')
            version=input('Before version ID or Git commit: ').strip();ident=input('Change event ID: ').strip();kind=input('Change kind [value_change / rule_change] (Enter=value_change): ').strip() or 'value_change'
            print('Prior applicability is not inferred from this quote or its Git date. This run will analyse the revised clause only.')
            if input('Use revised_clause_only analysis? [y/N]: ').strip().lower()!='y':raise ValueError('No scenario written. Supply reviewed prior scope using --event JSON for a full-scope comparison.')
            change={'id':ident,'kind':kind,'root_ko':n['key'],'changed_fields':changed,'analysis_basis':'revised_clause_only','before':{'version_id':version,'text':text,'source':{'file':str(source.resolve()),'sha256':hashlib.sha256(raw).hexdigest()}}}
            known_end=any(str(t['temporal_window'][1]).strip().lower() not in UNKNOWN for x in ns for t in x['ko']['applicability_tuples']) or any(str(t['temporal_window'][1]).strip().lower() not in UNKNOWN for e in es for t in e.get('applicability_tuples',[]))
            if known_end:
                change['end_date_convention']=input('All recorded end dates are inclusive or exclusive? (Mixed: cancel and use per-record --event JSON): ').strip()
                if change['end_date_convention'] not in ['inclusive','exclusive']:raise ValueError('Declare end-date semantics explicitly.')
            if len(n['ko']['applicability_tuples'])>1:
                for i,t in enumerate(n['ko']['applicability_tuples']):print(i,json.dumps(t))
                change['change_scope_case']=int(input('Change applicability case (zero-based): '))
        scenario=build(packet,change);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(scenario,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print('Saved:',args.output);print('Nodes:',len(scenario['nodes']),'edges:',len(scenario['relationships']),'omitted unverified records:',len(scenario['annotation_import']['omitted_unverified_records']))
        print('Unknown applicability may produce Defer. This is not evidence of a definite impact.')
    except (ValueError,KeyError,IndexError,OSError) as e:p.exit(2,'Scenario not created: '+str(e)+'\n')
if __name__=='__main__':main()
