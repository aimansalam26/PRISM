import unittest,copy,random
from engine import discover,validate,HANDBOOK_DIMENSIONS
from reference import compare
from test_engine import fixture,item

def handbook():
 s=fixture();s['schema_version']='0.4'
 for record in [s['event']['before'],s['event']['after'],*s['nodes'],*s['relationships']]:
  c=record['scope'];record['scope']={'employment_types':c['roles'],'org_roles':['*'],'entities':c['organisations'],'jurisdictions':c['jurisdictions'],'start':c['start'],'end':c['end']}
 c=s['event']['change_scope'];s['event']['change_scope']={'employment_types':c['roles'],'org_roles':['*'],'entities':c['organisations'],'jurisdictions':c['jurisdictions'],'start':c['start'],'end':c['end']}
 return s

class HandbookTests(unittest.TestCase):
 def check(self,s):
  r=discover(s);self.assertTrue(compare(s,r)['matches'],compare(s,r));return r
 def test_unknown_label_never_a_population(self):
  for s in [fixture(),handbook()]:
   s['nodes'][1]['scope']['jurisdictions']=['unknown']
   with self.assertRaises(ValueError):validate(s)
 def test_unknown_population_defers_not_definite_scope(self):
  s=handbook();s['nodes'][1]['scope']['org_roles']=None;r=self.check(s)
  self.assertEqual(item(r,'D')['status'],'Defer');self.assertEqual(item(r,'D')['affected_scopes'],[])
 def test_unknown_does_not_hide_known_jurisdiction_conflict(self):
  s=handbook();s['nodes'][1]['scope'].update(org_roles=None,jurisdictions=['NL']);s['nodes'][2]['scope']['jurisdictions']=['UK'];r=self.check(s)
  self.assertEqual(item(r,'B')['status'],'Defer');self.assertEqual(item(r,'C')['status'],'No')
 def test_unknown_dates_deferral_and_known_time_conflict(self):
  s=handbook();s['relationships'][0]['scope']['start']=None;self.assertEqual(item(self.check(s),'B')['status'],'Defer')
  s['relationships'][0]['scope']['end']='2026-01-01';self.assertEqual(item(self.check(s),'B')['status'],'No')
 def test_uncertain_review_only_is_terminal(self):
  s=fixture();s['relationships'][0].update(type='REVIEW_ONLY',certainty='uncertain',uncertainty_reason='Ambiguous link');r=self.check(s)
  self.assertEqual(item(r,'B')['status'],'Defer');self.assertEqual(item(r,'C')['status'],'No');self.assertEqual(item(r,'B')['paths'][0]['action'],'review_stop')
 def test_review_only_after_uncertain_path_is_terminal(self):
  s=fixture();s['relationships'][0].update(certainty='uncertain',uncertainty_reason='Unclear');s['relationships'][1]['type']='REVIEW_ONLY';r=self.check(s)
  self.assertEqual(item(r,'C')['status'],'Defer');self.assertEqual(item(r,'D')['status'],'No')
 def test_calculates_and_field_renaming(self):
  s=fixture();s['relationships'][0].update(type='CALCULATES_VALUE',field_mappings=[{'source_field':'amount','target_field':'deduction'}]);s['relationships'][1].update(field_mappings=[{'source_field':'deduction','target_field':'tax'}]);r=self.check(s)
  self.assertEqual(item(r,'C')['status'],'Yes');self.assertEqual(item(r,'D')['status'],'No');self.assertEqual(item(r,'C')['paths'][0]['field'],'deduction');self.assertEqual(item(r,'C')['paths'][0]['output_field'],'tax')
 def test_multiple_outputs_remain_separate(self):
  s=fixture();s['relationships'][0]['field_mappings']=[{'source_field':'amount','target_field':x} for x in ['amount','tax']];r=self.check(s);self.assertEqual(len(item(r,'B')['paths']),2)
 def test_unknown_adoption_guard_remains_uncertain(self):
  s=handbook();s['nodes'][1]['scope']['jurisdictions']=['IE'];s['relationships'][0].update(type='ADOPTS_VALUE',mapping={'from':{'jurisdictions':['UK']},'to':{'jurisdictions':['IE']}});s['event']['change_scope']['jurisdictions']=None;r=self.check(s);self.assertEqual(item(r,'B')['status'],'Defer')
 def test_correlated_root_cells_supported(self):
  s=handbook();a=copy.deepcopy(s['nodes'][0]['scope']);b=copy.deepcopy(a);a['jurisdictions']=['NL'];b['jurisdictions']=['UK']
  for record in [s['nodes'][0],s['event']['after'],s['event']['before']]:record.pop('scope');record['scope_cells']=[copy.deepcopy(a),copy.deepcopy(b)]
  self.assertEqual(len(item(self.check(s),'B')['affected_scopes']),2)
 def test_no_repeated_node_cycles(self):
  s=fixture();e=copy.deepcopy(s['relationships'][0]);e.update(id='BA',prerequisite='B',dependent='A');s['relationships'].append(e);r=self.check(s)
  self.assertTrue(any(d['reason']=='cycle_detected' for d in r['decisions']));self.assertTrue(all(len(p['node_path'])==len(set(p['node_path'])) for i in r['items'] for p in i['paths']))
 def test_random_unknown_and_mapping_reference_agreement(self):
  rng=random.Random(123)
  for _ in range(80):
   s=handbook()
   for n in s['nodes'][1:]:
    n['scope']['jurisdictions']=rng.choice([None,['NL'],['UK'],['*']]);n['scope']['org_roles']=rng.choice([None,['manager'],['*']])
   for e in s['relationships']:
    e['type']=rng.choice(['DEPENDS_ON','CALCULATES_VALUE','REVIEW_ONLY','RELATED_TO']);e['scope']['start']=rng.choice([None,'2027-01-01']);e['certainty']=rng.choice(['confirmed','uncertain']);e['uncertainty_reason']='Test uncertainty'
   self.check(s)
if __name__=='__main__':unittest.main()
