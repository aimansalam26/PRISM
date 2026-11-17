"""Offline validation regression checks; no API calls."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('classifier',Path(__file__).with_name('05_classify_edge_candidates.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
km={k:{'provenance':{'section_id':s},'semantics':{'watched_fields':[f]}} for k,s,f in [('A','S1','amount'),('B','S2','deduction')]}
sm={'S1':{'raw_text':'Cap is 2000.\r\n','line_start':10,'source_file':'a.md','source_sha256':'test'},'S2':{'raw_text':'Deduct the excess above the cap.','line_start':20,'source_file':'b.md','source_sha256':'test'}}
c={'candidate_id':'C1','ko_a_id':'A','ko_b_id':'B'}
base=dict(candidate_id='C1',outcome='proposed_relationship',upstream_ko_id='A',dependent_ko_id='B',relation_type='CALCULATES_VALUE',field_mappings=[dict(source_field='amount',target_field='deduction')],evidence=[dict(section_id='S2',quote='Deduct the excess above the cap.')],justification='The calculation uses the cap.')
def check(label,patch,valid):
 errors,_=m.validate_classification(m.CandidateClassification(**(base|patch)),c,km,sm)
 assert (not errors)==valid,(label,errors)
 print('PASS:',label)
check('valid proposal',{},True)
check('wrong pair',{'dependent_ko_id':'C'},False)
check('fabricated quote',{'evidence':[dict(section_id='S2',quote='Invented')]},False)
check('empty evidence',{'evidence':[]},False)
check('bad field',{'field_mappings':[dict(source_field='amount',target_field='wrong')]},False)
check('REVIEW_ONLY forbids mappings',{'relation_type':'REVIEW_ONLY'},False)
check('REVIEW_ONLY permits empty mappings',{'relation_type':'REVIEW_ONLY','field_mappings':[]},True)
check('unresolved conditions block export',{'review_constraints_notes':['Only if local approval exists']},False)
negative=dict(outcome='no_dependency',upstream_ko_id=None,dependent_ko_id=None,relation_type=None,field_mappings=[])
check('negative needs evidence',negative|{'evidence':[]},False)
check('negative evidence is checked',negative|{'evidence':[dict(section_id='S2',quote='Invented')]},False)
check('valid evidenced negative',negative,True)
check('unresolved may explain missing evidence',negative|{'outcome':'unresolved','evidence':[]},True)
assert m.locate_quote_span('Cap is 2000.\r\n',sm['S1'])==(10,10)
print('PASS: inclusive line span with trailing CRLF')
page=m.render_review([],{}, {},'test')
assert 'promoteToProposed' not in page and 'swapDirection' not in page
assert "'pending'" in page
page=m.render_review([{'test':'</script><script>bad()</script>'}],{}, {},'test')
assert '</script><script>bad()' not in page
print('PASS: pending defaults, no unsafe editing controls, escaped embedded data')
