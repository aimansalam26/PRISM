"""Conservative source-evidence gate. Text support is not a semantic scope proof."""
import copy,re
from datetime import date
DIMS=['employment_types','org_roles','entities','jurisdictions','temporal_window']
UNKNOWN={'unknown','unspecified','not stated',''}
ALIASES={
 'jurisdictions':{'NL':['netherlands','the netherlands','NL'],'UK':['united kingdom','UK'],'US':['united states','usa','US'],'BE':['belgium','BE'],'IE':['ireland','IE']},
 'employment_types':{'full_time':['full-time','full time'],'part_time':['part-time','part time'],'contractor':['contractor','contractors'],'intern':['intern','interns']},
 'entities':{'GitLab BV':['gitlab bv','gitlab b.v.'],'GitLab Ltd':['gitlab ltd','gitlab limited'],'GitLab Inc':['gitlab inc','gitlab inc.']}
}

def canonical_value(dim,value):
    value=str(value).strip()
    if value.lower() in UNKNOWN:return 'unknown'
    for canonical,aliases in ALIASES.get(dim,{}).items():
        if value.casefold() in {canonical.casefold(),*(x.casefold() for x in aliases)}:return canonical
    return value

def dimension_problem(dim,value):
    countries={x.casefold() for k,vs in ALIASES['jurisdictions'].items() for x in [k,*vs]}
    if dim=='entities' and value.casefold() in countries:return 'A country is not an employing entity. Select entity evidence (e.g. GitLab BV) or use unknown.'
    if dim=='org_roles' and value.lower().replace('_',' ') in ['team members','team member','employees','employee','staff']:
        return 'Generic staff wording does not identify a specific organisational role. Use unknown unless a role is stated.'
    return None

def reconcile(k,sections):
    """Repair aliases/citations without widening, clearing, or inventing scope."""
    new=copy.deepcopy(k)
    for t in new.get('applicability_tuples',[]):
        for dim in DIMS:
            t[dim]=[canonical_value(dim,v) for v in t.get(dim,[])]
            if dim!='temporal_window':t[dim]=list(dict.fromkeys(t[dim]))
    for r in new.get('scope_support',[]):r['value']=canonical_value(r.get('dimension'),r.get('value',''))
    new=suggested_evidence(new,sections)
    # Stale hidden references must not block an otherwise valid edit. Audit stores old record.
    new['scope_support']=[r['evidence'] for r in report(new,sections) if r['status']=='source_supported']
    return new

def scope_readiness(k,sections):
    rows=report(k,sections)
    unresolved=[{'tuple_index':r['tuple_index'],'dimension':r['dimension'],'position':r['position'],'value':r['value'],'status':r['status']} for r in rows if r['status']!='source_supported']
    if not rows:unresolved=[{'status':'missing_scope'}]
    return {'status':'scope_unresolved' if unresolved else 'scope_evidenced',
            'unresolved':unresolved,'engine_ready':False,
            'note':'Annotation approval is not engine admission. Unknown is neither universal nor empty. Resolve or explicitly defer uncertain paths in the engine adapter; validate fields, edges and final verification separately.'}

def supported_literal(dim,value,quote):
    value=canonical_value(dim,value)
    if str(value).lower() in UNKNOWN:return True
    if dimension_problem(dim,value):return False
    if str(value).lower() in ['all','any','*','everyone','global']:return False
    if dim=='temporal_window':
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):return False
            date.fromisoformat(value)
        except (ValueError,TypeError):return False
    # Country codes alone are not proof (e.g. "US" versus the pronoun "us").
    choices=ALIASES.get(dim,{}).get(value,[value.replace('_',' ')])
    if dim=='jurisdictions' and value not in ALIASES['jurisdictions']:return False
    for term in choices:
        flags=0 if term in ['UK','US','NL','BE','IE'] else re.I
        if re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',quote,flags):return True
    return False

def evidence_for(k,sections,i,dim,value):
    for r in k.get('scope_support',[]):
        if r.get('tuple_index')!=i or r.get('dimension')!=dim or r.get('value')!=value:continue
        s=sections.get(r.get('section_id'));q=r.get('quote','')
        if not s or not q or q not in s['raw_text']:continue
        # Citation must be the rule section or explicitly selected contextual evidence.
        if r['section_id']!=k.get('section_id') and not any(c.get('section_id')==r['section_id'] and q in c.get('quote','') for c in k.get('context_evidence',[])):continue
        if supported_literal(dim,value,q):return r
    return None

def report(k,sections):
    rows=[]
    for i,t in enumerate(k.get('applicability_tuples',[])):
        for dim in DIMS:
            for pos,value in enumerate(t.get(dim,[])):
                unknown=str(value).lower() in UNKNOWN;e=None if unknown else evidence_for(k,sections,i,dim,value)
                rows.append({'tuple_index':i,'dimension':dim,'value':value,'position':pos,'status':'unknown' if unknown else 'source_supported' if e else 'unsupported','evidence':e,'reason':dimension_problem(dim,str(value)) or ('No matching citation in the rule or selected context.' if not unknown and not e else '')})
    return rows

def normalize(k,sections):
    new=copy.deepcopy(k);rows=report(new,sections);changes=[]
    for r in rows:
        if r['status']=='unsupported':
            new['applicability_tuples'][r['tuple_index']][r['dimension']][r['position']]='unknown';changes.append(r)
    # Preserve tuple correlations and positional date endpoints; no flattening/cross product.
    for t in new.get('applicability_tuples',[]):
        for dim in DIMS[:-1]:t[dim]=list(dict.fromkeys(t.get(dim,['unknown'])))
    new['scope_support']=[r['evidence'] for r in rows if r['status']=='source_supported']
    new['scope_grounding_changes']=changes
    return new

def suggested_evidence(k,sections):
    """Draft citations from the KO's own quote and already selected context only."""
    new=copy.deepcopy(k);new.setdefault('scope_support',[])
    refs=[{'section_id':k['section_id'],'quote':k.get('source_quote','')}]+k.get('context_evidence',[])
    for row in report(k,sections):
        if row['status']!='unsupported':continue
        for r in refs:
            s=sections.get(r.get('section_id'));q=r.get('quote','')
            if s and q and q in s['raw_text'] and supported_literal(row['dimension'],row['value'],q):
                new['scope_support'].append({'tuple_index':row['tuple_index'],'dimension':row['dimension'],'value':row['value'],'section_id':r['section_id'],'quote':q});break
    return new

GUIDANCE='''Work as a careful compliance-policy analyst preparing drafts for a human verifier. Extract concrete entitlements, limits, requirements, exceptions and mandatory procedures. Generic promotional introductions such as "comprehensive coverage" are not eligibility rules. Do not fill gaps from external legal knowledge. Every non-unknown applicability value needs a scope_support entry: tuple_index (zero based), dimension, value, section_id, exact quote. If the quote comes from a heading or parent sentence, also cite that same quote in context_evidence and explain its relevance in scope_evidence. Retain correlated tuples; never combine unrelated eligibility alternatives into a Cartesian product. Heading/country mentions alone do not establish employment types, entities or dates. Netherlands is a jurisdiction, not an entity; GitLab BV is an entity. Generic team members is not a specific organisational role: use unknown for org_roles unless a specific role is stated. Unknown is correct when evidence is missing. Never use all/* or 9999-12-31 to fill missing bounds. Use ISO dates only when stated as policy applicability dates; leave creation dates and benefit deadlines out of effective-date scope. Source citations are proposals for human interpretation, not approval.'''
