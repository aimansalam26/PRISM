"""Small-graph correctness reference. Enumerates all bounded structural paths.

Independently implemented scope operations. Imports no traversal-engine code.
Agreement verifies the written computational specification, not policy truth.
"""
from copy import deepcopy

DIMS = ('roles', 'jurisdictions', 'organisations')


def evaluate(snapshot, max_hops=3):
    event = snapshot['event']
    nodes = {n['id']: n for n in snapshot['nodes']}
    root = event['root_ko']
    records = []

    def options(record):
        return record['scope_cells'] if 'scope_cells' in record else [record['scope']]

    def meet(a, b):
        r = {}
        for k in DIMS:
            if a[k] == ['*']: r[k] = sorted(b[k])
            elif b[k] == ['*']: r[k] = sorted(a[k])
            else: r[k] = sorted(x for x in a[k] if x in b[k])
            if not r[k]: return None
        r['start'], r['end'] = max(a['start'], b['start']), min(a['end'], b['end'])
        return r if r['start'] < r['end'] else None

    # Enumerate first, then evaluate each complete path independently from root.
    paths = [[]]
    for depth in range(max_hops):
        new = []
        for path in [p for p in paths if len(p) == depth]:
            tail = path[-1]['dependent'] if path else root
            new += [path+[e] for e in snapshot['relationships'] if e['prerequisite'] == tail]
        paths += new
    for path in paths[1:]:
        for field in event['changed_fields']:
            states = [(meet(event['change_scope'], event['after']['scope']), False)]
            action = None
            for index, edge in enumerate(path):
                next_states = []
                if edge['type']=='RELATED_TO' or edge['field'] != field:
                    states=[]; break
                for scope, uncertain in states:
                    if uncertain or edge['certainty']=='uncertain':
                        overlap = any(max(event['change_scope']['start'], a['start'], b['start']) < min(event['change_scope']['end'], a['end'], b['end']) for a in options(edge) for b in options(nodes[edge['dependent']]))
                        if overlap: next_states.append((None, True))
                        action='defer'
                    elif edge['type']=='OVERRIDES':
                        continue
                    else:
                        source=deepcopy(scope)
                        if edge['type']=='ADOPTS_VALUE':
                            guard={**{k:['*'] for k in DIMS}, **edge['mapping']['from'], 'start':event['change_scope']['start'], 'end':event['change_scope']['end']}
                            source=meet(source,guard)
                            if source is None:continue
                            source.update(deepcopy(edge['mapping']['to']))
                        for a in options(edge):
                            first=meet(source,a)
                            if first is None:continue
                            for b in options(nodes[edge['dependent']]):
                                last=meet(first,b)
                                if last:next_states.append((last,False))
                        action='review_stop' if edge['type']=='REVIEW_ONLY' else 'continue'
                states=next_states
                if not states:break
                if action=='review_stop' and index < len(path)-1:
                    states=[];break
            if path[-1]['dependent']==root:continue
            for scope, uncertain in states:
                record={'ko_id':path[-1]['dependent'], 'field':field, 'edge_path':[e['id'] for e in path], 'scope':scope, 'status':'Defer' if uncertain else 'Yes', 'action':action}
                if record not in records:records.append(record)
    return records


def compare(snapshot, result):
    import json
    actual=[]
    for item in result['items']:
        for p in item['paths']:
            actual.append({k:v for k,v in dict(ko_id=item['ko_id'],**p).items() if k in {'ko_id','field','edge_path','scope','status','action'}})
    normalize=lambda rows:{json.dumps(x,sort_keys=True) for x in rows}
    expected=normalize(evaluate(snapshot,result['max_hops']))
    observed=normalize(actual)
    return {'matches':expected==observed,'missing':sorted(expected-observed),'unexpected':sorted(observed-expected)}
