import copy,json,tempfile,sqlite3,unittest
from pathlib import Path
from graph_store import GraphStore,fingerprint
from app import KO,check
import scope_grounding as sg
import final_review as fr
from extraction import section_selection

class GroundingTests(unittest.TestCase):
 def setUp(self):
  self.sections={'S':{'raw_text':'Full-time Netherlands team members receive EUR 150.'},'H':{'raw_text':'title: GitLab BV (Netherlands) Benefits'}}
  self.k={'section_id':'S','source_quote':self.sections['S']['raw_text'],'context_evidence':[],'applicability_tuples':[{'employment_types':['full_time'],'org_roles':['unknown'],'entities':['GitLab BV'],'jurisdictions':['NL'],'temporal_window':['2026-01-01','9999-12-31']}],'scope_support':[]}
 def test_unsupported_cleared_not_assumed(self):
  x=sg.normalize(self.k,self.sections);self.assertEqual(x['applicability_tuples'][0]['jurisdictions'],['unknown']);self.assertEqual(x['applicability_tuples'][0]['temporal_window'],['unknown','unknown']);self.assertEqual(self.k['applicability_tuples'][0]['jurisdictions'],['NL'])
 def test_literals_and_explicit_context_only(self):
  x=sg.suggested_evidence(self.k,self.sections);x=sg.normalize(x,self.sections);self.assertEqual(x['applicability_tuples'][0]['jurisdictions'],['NL']);self.assertEqual(x['applicability_tuples'][0]['employment_types'],['full_time']);self.assertEqual(x['applicability_tuples'][0]['entities'],['unknown'])
  self.k['context_evidence']=[{'section_id':'H','quote':'GitLab BV (Netherlands)','purpose':'scope'}];x=sg.normalize(sg.suggested_evidence(self.k,self.sections),self.sections);self.assertEqual(x['applicability_tuples'][0]['entities'],['GitLab BV'])
 def test_forged_context_and_all_not_allowed(self):
  self.k['scope_support']=[{'tuple_index':0,'dimension':'entities','value':'GitLab BV','section_id':'H','quote':'GitLab BV'}]
  self.assertIsNone(sg.evidence_for(self.k,self.sections,0,'entities','GitLab BV'));self.assertFalse(sg.supported_literal('jurisdictions','US','Contact us'));self.assertFalse(sg.supported_literal('employment_types','all','all staff'));self.assertFalse(sg.supported_literal('temporal_window','2026-02-30','2026-02-30'));self.assertFalse(sg.supported_literal('temporal_window','2026','from 2026'))
 def test_tuple_correlations_preserved(self):
  self.k['applicability_tuples'].append({'employment_types':['contractor'],'org_roles':['unknown'],'entities':['unknown'],'jurisdictions':['UK'],'temporal_window':['unknown','unknown']})
  x=sg.normalize(sg.suggested_evidence(self.k,self.sections),self.sections);self.assertEqual(len(x['applicability_tuples']),2);self.assertEqual(x['applicability_tuples'][1]['jurisdictions'],['unknown']);self.assertEqual(x['applicability_tuples'][0]['jurisdictions'],['NL'])
 def test_topic_selection(self):
  ss=[{'heading_path':['Benefits','Medical Allowance']},{'heading_path':['Benefits','Medical Allowance'],'disclosure_title':'Eligibility'},{'heading_path':['Benefits','Bike']}]
  self.assertEqual(section_selection('topic:Medical Allowance',ss),[0,1])
  with self.assertRaises(ValueError):section_selection('topic:missing',ss)

class FinalTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.p=self.root/'pilot';self.p.mkdir()
  s={'section_id':'S','raw_text':'Minimum 20 vacation days annually.','line_start':1,'line_end':1,'heading_path':['Leave'],'source_file':'leave.md','source_sha256':'abc'};self.s=s
  (self.p/'manifest.json').write_text(json.dumps({'source_file':'/handbook/leave.md','source_sha256':'abc'}));(self.p/'parsed_sections.json').write_text(json.dumps([s]));self.db=sqlite3.connect(self.p/'annotations.sqlite');self.db.execute('CREATE TABLE state(id TEXT PRIMARY KEY,body TEXT)')
  k=KO(section_id='S',summary='Annual leave minimum is 20 days.',source_quote=s['raw_text'],watched_fields=['leave_days'],applicability_tuples=[{'employment_types':['unknown'],'org_roles':['unknown'],'entities':['unknown'],'jurisdictions':['unknown'],'temporal_window':['unknown','unknown']}],scope_evidence='',additional_conditions=[]).model_dump();k.update(id='K1',status='approved',validation_errors=[]);self.k=k
  self.db.execute('INSERT INTO state VALUES (?,?)',('K1',json.dumps(k)));self.db.commit();self.graph=GraphStore(self.root)
 def tearDown(self):self.graph.db.close();self.db.close();self.tmp.cleanup()
 def accept(self,item,checked=True):return fr.decide(self.graph,{'id':item['id'],'fingerprint':item['fingerprint'],'decision':'accept','reason':'matches_source','evidence_checked':checked},'Verifier',check)
 def test_no_typing_and_no_auto_approval(self):
  item=fr.packet(self.graph,check)['items'][0];self.assertEqual(item['decision'],'pending')
  with self.assertRaises(ValueError):self.accept(item,False)
  result=self.accept(item);self.assertEqual(result['comment'],'');self.assertEqual(fr.packet(self.graph,check)['counts']['accepted'],1)
 def test_content_change_invalidates_verification(self):
  item=fr.packet(self.graph,check)['items'][0];self.accept(item);self.k['summary']='Changed summary';self.db.execute('UPDATE state SET body=?',(json.dumps(self.k),));self.db.commit();self.assertEqual(fr.packet(self.graph,check)['counts']['accepted'],0)
  with self.assertRaises(ValueError):self.accept(item)
 def test_old_unsupported_scope_blocked(self):
  self.k['applicability_tuples'][0]['jurisdictions']=['NL'];self.db.execute('UPDATE state SET body=?',(json.dumps(self.k),));self.db.commit();item=fr.packet(self.graph,check)['items'][0];self.assertTrue(item['errors'])
  with self.assertRaises(ValueError):self.accept(item)
 def test_edge_waits_for_endpoint_verification(self):
  k=copy.deepcopy(self.k);k['id']='K2';self.db.execute('INSERT INTO state VALUES (?,?)',('K2',json.dumps(k)));self.db.commit()
  self.graph.save_edge({'source':'pilot::K1','target':'pilot::K2','relation_type':'REVIEW_ONLY','trigger_fields':['leave_days'],'status':'approved','justification':'Fixture: related guidance','field_mappings':[],'dimension_mapping':[]},'Curator')
  items=fr.packet(self.graph,check)['items'];edge=next(i for i in items if i['kind']=='edge')
  with self.assertRaises(ValueError):self.accept(edge)
  for item in items:
   if item['kind']=='ko':self.accept(item)
  edge=next(i for i in fr.packet(self.graph,check)['items'] if i['kind']=='edge');self.accept(edge);self.assertEqual(fr.packet(self.graph,check)['counts']['accepted'],3)
if __name__=='__main__':unittest.main()
