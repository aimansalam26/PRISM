"""PRISM 0.3.0. Explicit unknown scope, field transfer and terminal review.
Schema 0.3 remains readable; schema 0.4 keeps employment and job roles separate.
Unknown is represented by null, never by a population identifier or wildcard.
"""
from collections import defaultdict,deque
from copy import deepcopy
from datetime import date
import hashlib,json
VERSION='0.3.0'
DIMENSIONS=('roles','jurisdictions','organisations')
HANDBOOK_DIMENSIONS=('employment_types','org_roles','entities','jurisdictions')
TYPES={'DEPENDS_ON','CALCULATES_VALUE','RELATED_TO','ADOPTS_VALUE','OVERRIDES','REVIEW_ONLY'}
PROPAGATIVE={'DEPENDS_ON','CALCULATES_VALUE','ADOPTS_VALUE'}
MODES=('prism','local','untyped')
UNKNOWN_LABELS={'unknown','unspecified','not stated','all_dimensions','all_roles','global'}

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def dimensions(scope):return HANDBOOK_DIMENSIONS if isinstance(scope,dict) and 'employment_types' in scope else DIMENSIONS

def check_scope(scope):
    if not isinstance(scope,dict):raise ValueError('Scope must be an object.')
    dims=dimensions(scope);allow_unknown=dims==HANDBOOK_DIMENSIONS
    if set(scope)!=set(dims)|{'start','end'}:raise ValueError('Scope must contain exactly its population dimensions and start/end.')
    for d in dims:
        values=scope[d]
        if values is None and allow_unknown:continue
        if not isinstance(values,list) or not values or any(not isinstance(x,str) or not x.strip() for x in values):raise ValueError('Scope '+d+' must contain nonempty identifiers (or null in schema 0.4).')
        if any(x.strip().lower() in UNKNOWN_LABELS for x in values):raise ValueError('Unknown/legacy scope labels are not populations. Use explicit null in schema 0.4.')
        if len(set(values))!=len(values) or ('*' in values and len(values)!=1):raise ValueError('Use unique identifiers or an explicit standalone wildcard.')
    for key in ['start','end']:
        x=scope[key]
        if x is None and allow_unknown:continue
        try:
            if not isinstance(x,str) or date.fromisoformat(x).isoformat()!=x:raise ValueError('Noncanonical date.')
        except (TypeError,ValueError):raise ValueError('Scope dates must be ISO YYYY-MM-DD (or null in schema 0.4).') from None
    if scope['start'] is not None and scope['end'] is not None and scope['start']>=scope['end']:raise ValueError('Scope start must precede end (end is exclusive).')

def cells(record):
    if not isinstance(record,dict):return [None]
    return record.get('scope_cells',[record.get('scope')])

def has_unknown(scope):return any(v is None for v in scope.values())

def intersection(*scopes):
    """Possible intersection bounds. Caller must retain uncertainty separately."""
    result=deepcopy(scopes[0]);dims=dimensions(result)
    for other in scopes[1:]:
        if dimensions(other)!=dims:raise ValueError('Cannot mix scope schemas.')
        for d in dims:
            a,b=result[d],other[d]
            if a is None:value=deepcopy(b)
            elif b is None:value=deepcopy(a)
            else:
                aset,bset=set(a),set(b);value=sorted(bset if '*' in aset else aset if '*' in bset else aset&bset)
                if not value:return None
            result[d]=value
        starts=[x for x in [result['start'],other['start']] if x is not None]
        ends=[x for x in [result['end'],other['end']] if x is not None]
        result['start']=max(starts) if starts else None;result['end']=min(ends) if ends else None
        if result['start'] is not None and result['end'] is not None and result['start']>=result['end']:return None
    return result

def time_window(scope):return {**{d:['*'] for d in dimensions(scope)},'start':scope['start'],'end':scope['end']}

def trigger_fields(edge):
    if edge.get('field_mappings'):return list(dict.fromkeys(m.get('source_field') for m in edge['field_mappings']))
    return edge.get('trigger_fields') or ([edge['field']] if edge.get('field') else [])

def output_fields(edge,field):
    if edge['type'] not in PROPAGATIVE:return [field]
    if 'field_mappings' in edge:return list(dict.fromkeys(m['target_field'] for m in edge['field_mappings'] if m['source_field']==field))
    return [field]

def validate(snapshot):
    if snapshot.get("schema_version") not in {"0.3", "0.4"}:
        raise ValueError("Expected schema_version 0.3 (legacy) or 0.4 (handbook).")
    expected_dims = DIMENSIONS if snapshot["schema_version"]=="0.3" else HANDBOOK_DIMENSIONS
    def validate_cell(c):
        check_scope(c)
        if dimensions(c)!=expected_dims:raise ValueError("Scope dimensions do not match the scenario schema.")
    event = snapshot.get("event", {})
    if event.get("kind") not in {"value_change", "rule_change"}:
        raise ValueError("Only value_change and rule_change are supported.")
    if event.get("scope_change") or event.get("relationship_changes"):
        raise ValueError("Withdrawal/scope or relationship changes require dual snapshots; unsupported in 0.3.0.")
    fields = event.get("changed_fields")
    if not isinstance(fields, list) or not fields or any(not isinstance(x, str) or not x for x in fields) or len(set(fields)) != len(fields):
        raise ValueError("changed_fields must be unique nonempty identifiers.")
    validate_cell(event.get("change_scope"))
    after, before = event.get("after", {}), event.get("before", {})
    for record in (before,after):
        if not cells(record):raise ValueError('Before and after require scope cells.')
        for c in cells(record):validate_cell(c)
    if before.get("scope_known", True):
        pop=lambda record:sorted(json.dumps({d:c[d] for d in expected_dims},sort_keys=True) for c in cells(record))
        if pop(before)!=pop(after):raise ValueError('Old/new population differs: scope-change discovery is unsupported.')
    elif event.get('analysis_basis')!='revised_clause_only':
        raise ValueError('Unknown prior scope requires explicit revised_clause_only analysis.')
    if not before.get('version_id') or not after.get('version_id') or before['version_id']==after['version_id']:
        raise ValueError('Before and after need distinct nonempty version IDs.')
    nodes = snapshot.get("nodes", [])
    ids = [n.get("id") for n in nodes]
    if not ids or any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("Node IDs must be unique and nonempty.")
    root = event.get("root_ko")
    if root not in ids or root != after.get("version_id"):
        raise ValueError("root_ko must be the revised version present in nodes.")
    for n in nodes:
        if not n.get("title") or not n.get("text") or not n.get("source"):
            raise ValueError(f"Missing text/provenance on {n['id']}.")
        if "scope" in n and "scope_cells" in n:
            raise ValueError("Use scope OR scope_cells.")
        if not cells(n):
            raise ValueError("At least one scope cell is required.")
        for c in cells(n):
            validate_cell(c)
    node_map = {n["id"]: n for n in nodes}
    if node_map[root]["text"] != after.get("text") or cells(node_map[root]) != cells(after):
        raise ValueError("Root text/scope must match revised evidence.")
    if not any(intersection(c,event["change_scope"]) for c in cells(after)):
        raise ValueError("Change scope does not overlap the revised root.")
    edge_ids = set()
    for e in snapshot.get("relationships", []):
        if not e.get("id") or e["id"] in edge_ids:
            raise ValueError("Relationship IDs must be unique and nonempty.")
        edge_ids.add(e["id"])
        if e.get("prerequisite") not in ids or e.get("dependent") not in ids:
            raise ValueError(f"Unknown endpoint on {e['id']}.")
        if e.get("type") not in TYPES or not e.get("source") or not e.get("evidence"):
            raise ValueError(f"Unsupported type or missing source/evidence on {e['id']}.")
        if 'field_mappings' in e and (not isinstance(e['field_mappings'],list) or any(not isinstance(m,dict) for m in e['field_mappings'])):raise ValueError('field_mappings must be a list of objects.')
        if e['type']!='RELATED_TO':
            fields_in=trigger_fields(e)
            if not fields_in or any(not isinstance(f,str) or not f.strip() for f in fields_in):raise ValueError('Relationship needs explicit trigger fields: '+e['id'])
            if len(set(fields_in))!=len(fields_in):raise ValueError('Duplicate trigger fields.')
        mappings=e.get('field_mappings')
        if mappings is not None:
            if not isinstance(mappings,list):raise ValueError('field_mappings must be a list.')
            if e['type'] in PROPAGATIVE and not mappings:raise ValueError('Propagative edges need field mappings.')
            if e['type'] not in PROPAGATIVE and mappings:raise ValueError('Terminal/blocked links cannot propagate mapped fields.')
            for m in mappings:
                if not isinstance(m,dict) or any(not isinstance(m.get(k),str) or not m[k].strip() for k in ['source_field','target_field']):raise ValueError('Invalid field mapping.')
                for end,key in [('prerequisite','source_field'),('dependent','target_field')]:
                    declared=node_map[e[end]].get('watched_fields')
                    if declared is not None and m[key] not in declared:raise ValueError('Mapping references an undeclared watched field.')
        if e.get("certainty") not in {"confirmed", "uncertain"}:
            raise ValueError(f"Declare confirmed or uncertain certainty on {e['id']}.")
        if e["certainty"] == "uncertain" and not e.get("uncertainty_reason"):
            raise ValueError("Uncertain relationships need a reason.")
        if e["type"] == "OVERRIDES" and e.get("override_mode") != "independent_value":
            raise ValueError("Only explicitly independent fixed-value overrides are supported.")
        if e["type"] in {"OVERRIDES", "ADOPTS_VALUE"} and event["kind"] != "value_change":
            raise ValueError("Value adoption/replacement is limited to value_change events in this release.")
        if e["type"] == "ADOPTS_VALUE":
            mapping = e.get("mapping", {})
            if not mapping.get("from") or set(mapping.get("from", {})) != set(mapping.get("to", {})):
                raise ValueError("Adoption requires matching source/target mapped dimensions.")
            for side in ("from", "to"):
                for d, v in mapping[side].items():
                    if d not in expected_dims:
                        raise ValueError("Adoption maps population dimensions, never dates.")
                    validate_cell({**time_window(event["change_scope"]), d: v})
        if "scope" in e and "scope_cells" in e:
            raise ValueError("Use scope OR scope_cells on relationships.")
        if not cells(e):
            raise ValueError("Relationship scope cells cannot be empty.")
        for c in cells(e):
            validate_cell(c)
    # Priority resolution is deliberately outside this prototype. A confirmed
    # independent replacement and inheritance must have disjoint scopes.
    for override in snapshot.get("relationships", []):
        if override['type'] != 'OVERRIDES' or override['certainty'] != 'confirmed':
            continue
        for edge in snapshot['relationships']:
            if edge['type'] not in {'DEPENDS_ON','CALCULATES_VALUE','REVIEW_ONLY'} or edge['certainty'] != 'confirmed':
                continue
            if all(edge[k] == override[k] for k in ('prerequisite','dependent')) and set(trigger_fields(edge)) & set(trigger_fields(override)):
                if any(intersection(a,b) for a in cells(edge) for b in cells(override)):
                    raise ValueError('Overlapping inheritance and independent replacement: curate disjoint scopes or mark uncertainty.')
    return node_map


def transfer_states(scope,edge,target,window):
    source=deepcopy(scope);unknown=has_unknown(source)
    if edge['type']=='ADOPTS_VALUE':
        source=intersection(source,{**time_window(window),**edge['mapping']['from']})
        if source is None:return []
        source.update(deepcopy(edge['mapping']['to']))
    out=[]
    for ec in cells(edge):
        for nc in cells(target):
            x=intersection(source,ec,nc)
            state=(x,unknown or has_unknown(ec) or has_unknown(nc))
            if x is not None and state not in out:out.append(state)
    return out

def transfer(scope,edge,target,window):return [s for s,u in transfer_states(scope,edge,target,window)]

def discover(snapshot,mode='prism',max_hops=3):
    nodes=validate(snapshot)
    if mode not in MODES or type(max_hops) is not int or not 1<=max_hops<=3:raise ValueError('Use prism/local/untyped and max_hops 1–3.')
    event=snapshot['event'];root=event['root_ko'];adj=defaultdict(list)
    for e in sorted(snapshot.get('relationships',[]),key=lambda e:e['id']):adj[e['prerequisite']].append(e)
    queue=deque()
    for c in cells(event['after']):
        initial=intersection(event['change_scope'],c)
        if initial:
            for f in sorted(event['changed_fields']):queue.append((root,initial,f,[],[root],has_unknown(c) or has_unknown(event['change_scope']),False))
    paths=defaultdict(list);decisions=[];visited=0
    while queue:
        current,accumulated,field,edge_path,node_path,uncertain,link_uncertain=queue.popleft();visited+=1
        if len(edge_path)>=max_hops:continue
        for e in adj[current]:
            target=e['dependent'];next_edges=edge_path+[e['id']];next_nodes=node_path+[target]
            base_decision={'edge_path':next_edges,'node_path':next_nodes,'field':field,'edge_id':e['id'],'source':e['source'],'evidence':e['evidence']}
            if target in node_path:
                decisions.append(dict(base_decision,action='exclude',reason='cycle_detected',surviving_scopes=[]));continue
            if mode!='untyped' and (e['type']=='RELATED_TO' or field not in trigger_fields(e)):
                decisions.append(dict(base_decision,action='exclude',reason='unrelated_changed_field',surviving_scopes=[]));continue
            if mode!='untyped' and e['type']=='OVERRIDES' and e['certainty']=='confirmed':
                decisions.append(dict(base_decision,action='exclude',reason='independent_replacement_of_changed_value',surviving_scopes=[]));continue
            relation_uncertain=link_uncertain or e['certainty']=='uncertain'
            outputs=[]
            if mode=='untyped':outputs=[(None,False)]
            elif relation_uncertain:
                # An uncertain dependency can undermine population pruning. Retain only
                # the possible temporal bounds and mark the path unresolved.
                for ec in cells(e):
                    for nc in cells(nodes[target]):
                        x=intersection(time_window(accumulated),time_window(ec),time_window(nc))
                        if x is not None and (x,True) not in outputs:outputs.append((x,True))
            else:
                bases=[accumulated] if mode=='prism' or not edge_path else [intersection(c,time_window(event['change_scope'])) for c in cells(nodes[current])]
                for base in bases:
                    if base is not None:
                        for x,u in transfer_states(base,e,nodes[target],event['change_scope']):
                            pair=(x,u or uncertain)
                            if pair not in outputs:outputs.append(pair)
            if not outputs:
                decisions.append(dict(base_decision,action='exclude',reason='empty_scope_or_inactive_interval',surviving_scopes=[]));continue
            mapped=[field] if mode=='untyped' else output_fields(e,field)
            for next_field in mapped:
                terminal=mode!='untyped' and e['type'] in {'REVIEW_ONLY','OVERRIDES'}
                for scope,u in outputs:
                    status='Defer' if u and mode!='untyped' else 'Yes'
                    action='review_stop' if terminal else 'defer' if status=='Defer' else 'continue'
                    reason=e.get('uncertainty_reason','upstream_uncertainty') if relation_uncertain and mode!='untyped' else 'unknown_applicability' if status=='Defer' else 'structural_reachability' if mode=='untyped' else 'supported_dependency'
                    d=dict(base_decision,output_field=next_field if not terminal else None,action=action,reason=reason,surviving_scopes=[scope] if scope is not None and status=='Yes' else [])
                    if d not in decisions:decisions.append(d)
                    trace=dict(deepcopy(d),scope=scope if status=='Yes' else None,possible_scope=scope if status=='Defer' and not relation_uncertain else None,status=status,hops=len(next_edges))
                    if trace not in paths[target]:paths[target].append(trace)
                    if not terminal:queue.append((target,scope,next_field,next_edges,next_nodes,status=='Defer',relation_uncertain if mode!='untyped' else False))
    items=[]
    for ident in sorted(set(nodes)-{root}):
        traces=paths[ident];definite=[p for p in traces if p['status']=='Yes'];scopes=[]
        for p in definite:
            if p['scope'] is not None and p['scope'] not in scopes:scopes.append(p['scope'])
        items.append({'ko_id':ident,'title':nodes[ident]['title'],'status':'Yes' if definite else 'Defer' if traces else 'No','directness':('direct' if any(p['hops']==1 for p in definite) else 'indirect') if definite else 'unresolved' if traces else 'none','affected_scopes':scopes,'has_uncertainty':any(p['status']=='Defer' for p in traces),'paths':traces})
    return {'prototype_version':VERSION,'snapshot_id':snapshot.get('snapshot_id',snapshot.get('id')),'input_sha256':fingerprint(snapshot),'mode':mode,'max_hops':max_hops,'scope_supported':mode!='untyped','items':items,'decisions':decisions,'visited_states':visited,'review_volume':sum(i['status'] in {'Yes','Defer'} for i in items)}
