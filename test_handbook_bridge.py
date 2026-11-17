"""Synthetic bridge fixtures, not policy gold labels."""
import copy,unittest
from unittest.mock import patch
from build_handbook_scenario import build,annotation_hash,scope_cell
from engine import discover
from reference import compare
import evaluate

def packet():
 tuples=[{d:['unknown'] for d in ['employment_types','org_roles','entities','jurisdictions']}|{'temporal_window':['unknown','unknown']}]
 nodes=[];items=[]
 for key,quote,field in [('pilot::KO_A','Allowance is EUR 150.','amount'),('pilot::KO_B','Deduction uses the allowance.','deduction')]:
  k={'id':key.split('::')[1],'section_id':'S','status':'approved','summary':quote,'source_quote':quote,'watched_fields':[field],'applicability_tuples':copy.deepcopy(tuples)}
  fp=annotation_hash(k);n={'key':key,'ko':k,'fingerprint':fp,'source_sha256':'fixture-hash','source_file':'synthetic-fixture.md','section':{'raw_text':quote},'errors':[]};nodes.append(n)
  version=annotation_hash([fp,n['source_sha256']]);items.append({'id':'ko:'+key,'key':key,'fingerprint':version,'current':True,'decision':'accept','errors':[],'review':{'fingerprint':version},'scope':[]})
 e={'id':'E1','source':nodes[0]['key'],'target':nodes[1]['key'],'relation_type':'CALCULATES_VALUE','field_mappings':[{'source_field':'amount','target_field':'deduction'}],'certainty':'confirmed','effective_status':'approved','status':'approved','stale':False,'justification':'Synthetic test dependency','evidence':[{'quote':n['ko']['source_quote']} for n in nodes],'applicability_tuples':copy.deepcopy(tuples)}
 result={'graph':{'nodes':nodes,'edges':[e]},'items':items};refresh_edge(result);return result

def refresh_edge(p):
 p['items']=[i for i in p['items'] if not i['id'].startswith('edge:')];e=p['graph']['edges'][0];bykey={i['key']:i for i in p['items']};fp=annotation_hash([e,[(k,bykey[k]['fingerprint']) for k in [e['source'],e['target']]]]);p['items'].append({'id':'edge:E1','fingerprint':fp,'current':True,'decision':'accept','errors':[],'review':{'fingerprint':fp}})
def event():return {'id':'HB-TEST','root_ko':'pilot::KO_A','changed_fields':['amount'],'kind':'value_change','analysis_basis':'revised_clause_only','before':{'version_id':'before-fixture','text':'Allowance is EUR 100.','source':'synthetic-before.md'}}

class BridgeTests(unittest.TestCase):
 def test_end_date_convention_is_explicit(self):
  t=copy.deepcopy(packet()['graph']['nodes'][0]['ko']['applicability_tuples'][0]);t['temporal_window']=['2026-01-01','2026-12-31']
  with self.assertRaisesRegex(ValueError,'end_date_convention'):scope_cell(t)
  self.assertEqual(scope_cell(t,'inclusive')['end'],'2027-01-01')
  self.assertEqual(scope_cell(t,'exclusive')['end'],'2026-12-31')
  self.assertEqual(t['temporal_window'][1],'2026-12-31')
 def test_verified_packet_builds_runnable_unknown_scope_scenario(self):
  s=build(packet(),event());r=discover(s);self.assertEqual(r['items'][0]['status'],'Defer');self.assertTrue(compare(s,r)['matches']);self.assertEqual(s['event']['root_ko'],'HB-TEST::pilot::KO_A');self.assertIsNone(s['nodes'][0]['scope_cells'][0]['start'])
 def test_changed_record_invalidates_packet(self):
  p=packet();p['graph']['nodes'][0]['ko']['summary']='Changed'
  with self.assertRaisesRegex(ValueError,'changed'):build(p,event())
 def test_unverified_root_is_blocked(self):
  p=packet();p['items'][0]['decision']='pending'
  with self.assertRaises(ValueError):build(p,event())
 def test_unverified_edges_are_explicitly_omitted(self):
  p=packet();p['items'][-1]['decision']='pending';s=build(p,event());self.assertEqual(s['relationships'],[]);self.assertIn('E1',s['annotation_import']['omitted_unverified_records'])
 def test_terminal_requires_explicit_trigger_field(self):
  p=packet();e=p['graph']['edges'][0];e.update(relation_type='REVIEW_ONLY',field_mappings=[]);refresh_edge(p)
  with self.assertRaisesRegex(ValueError,'trigger'):build(p,event())
  e['trigger_fields']=['amount'];refresh_edge(p);self.assertEqual(discover(build(p,event()))['items'][0]['paths'][0]['action'],'review_stop')
 def test_no_before_evidence_or_fake_wildcard(self):
  e=event();e['before'].pop('source')
  with self.assertRaises(ValueError):build(packet(),e)
  t=copy.deepcopy(packet()['graph']['nodes'][0]['ko']['applicability_tuples'][0]);t['entities']=['*']
  with self.assertRaises(ValueError):scope_cell(t)
 def test_unsupported_change_is_not_silently_discarded(self):
  e=event();e['scope_change']=True
  with self.assertRaisesRegex(ValueError,'unsupported'):build(packet(),e)
 def test_empirical_ko_ids_in_gold_reader(self):
  suite={'scenarios':[{'event':{'root_ko':'ROOT'},'nodes':[{'id':'ROOT'},{'id':'HB::KO_A'}]}]}
  labels={'A1':'KO ID','A2':'HB::KO_A','F2':'Yes','H2':'Yes','G2':'Source','I2':'Source','K2':'Yes','L2':'Source quote','P2':'direct'}
  with patch.object(evaluate,'read_xlsx',return_value={'Legend':{'B20':'2026-11-17','B22':evaluate.fingerprint(suite)},'Labels':labels}):self.assertEqual(evaluate.read_gold('unused.xlsx',suite)['HB::KO_A']['label'],'Yes')
if __name__=='__main__':unittest.main()
