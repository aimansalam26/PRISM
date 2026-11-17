"""Independent bounded-path reference for PRISM 0.3.0; imports no engine code."""
from copy import deepcopy
import json

def evaluate(snapshot,max_hops=3):
    event=snapshot['event'];nodes={n['id']:n for n in snapshot['nodes']};root=event['root_ko'];records=[]
    dims=('employment_types','org_roles','entities','jurisdictions') if snapshot['schema_version']=='0.4' else ('roles','jurisdictions','organisations')
    def options(r):return r['scope_cells'] if 'scope_cells' in r else [r['scope']]
    def unknown(s):return None in s.values()
    def meet(a,b):
        result={}
        for d in dims:
            if a[d] is None:result[d]=deepcopy(b[d])
            elif b[d] is None:result[d]=deepcopy(a[d])
            elif a[d]==['*']:result[d]=sorted(b[d])
            elif b[d]==['*']:result[d]=sorted(a[d])
            else:
                result[d]=sorted(x for x in a[d] if x in b[d])
                if not result[d]:return None
        starts=[x for x in [a['start'],b['start']] if x is not None];ends=[x for x in [a['end'],b['end']] if x is not None]
        result['start']=max(starts) if starts else None;result['end']=min(ends) if ends else None
        return None if result['start'] is not None and result['end'] is not None and result['start']>=result['end'] else result
    def timed(s):return {**{d:['*'] for d in dims},'start':s['start'],'end':s['end']}
    paths=[[]]
    for depth in range(max_hops):
        more=[]
        for p in [p for p in paths if len(p)==depth]:
            tail=p[-1]['dependent'] if p else root;seen={root,*[e['dependent'] for e in p]}
            more.extend(p+[e] for e in snapshot['relationships'] if e['prerequisite']==tail and e['dependent'] not in seen)
        paths+=more
    for path in paths[1:]:
        for initial_field in event['changed_fields']:
            states=[]
            for c in options(event['after']):
                first=meet(event['change_scope'],c)
                if first is not None:states.append((first,unknown(c) or unknown(event['change_scope']),False,initial_field,None))
            for index,e in enumerate(path):
                next_states=[];terminal=e['type'] in ['REVIEW_ONLY','OVERRIDES']
                for scope,uncertain,link_uncertain,field,_ in states:
                    triggers=list(dict.fromkeys(m['source_field'] for m in e['field_mappings'])) if e.get('field_mappings') else e.get('trigger_fields') or ([e['field']] if e.get('field') else [])
                    if e['type']=='RELATED_TO' or field not in triggers:continue
                    if e['type']=='OVERRIDES' and e['certainty']=='confirmed':continue
                    weak=link_uncertain or e['certainty']=='uncertain';outputs=[]
                    if weak:
                        for ec in options(e):
                            a=meet(timed(scope),timed(ec))
                            if a is None:continue
                            for nc in options(nodes[e['dependent']]):
                                b=meet(a,timed(nc))
                                if b is not None:outputs.append((b,True))
                    else:
                        source=deepcopy(scope);u=unknown(source)
                        if e['type']=='ADOPTS_VALUE':
                            source=meet(source,{**timed(event['change_scope']),**e['mapping']['from']})
                            if source is None:continue
                            source.update(deepcopy(e['mapping']['to']))
                        for ec in options(e):
                            a=meet(source,ec)
                            if a is None:continue
                            for nc in options(nodes[e['dependent']]):
                                b=meet(a,nc)
                                if b is not None:outputs.append((b,uncertain or u or unknown(ec) or unknown(nc)))
                    outputs_fields=[field] if terminal or 'field_mappings' not in e else list(dict.fromkeys(m['target_field'] for m in e['field_mappings'] if m['source_field']==field))
                    for b,u in outputs:
                        for out_field in outputs_fields:
                            action='review_stop' if terminal else 'defer' if u else 'continue'
                            if index==len(path)-1:
                                row={'ko_id':e['dependent'],'field':field,'output_field':None if terminal else out_field,'edge_path':[x['id'] for x in path],'scope':None if u else b,'status':'Defer' if u else 'Yes','action':action}
                                if row not in records:records.append(row)
                            elif not terminal:next_states.append((b,u,weak,out_field,action))
                states=next_states
                if not states:break
    return records

def compare(snapshot,result):
    keys={'ko_id','field','output_field','edge_path','scope','status','action'}
    actual=[{k:v for k,v in dict(ko_id=i['ko_id'],**p).items() if k in keys} for i in result['items'] for p in i['paths']]
    norm=lambda rows:{json.dumps(x,sort_keys=True) for x in rows}
    expected=norm(evaluate(snapshot,result['max_hops']));observed=norm(actual)
    return {'matches':expected==observed,'missing':sorted(expected-observed),'unexpected':sorted(observed-expected)}
