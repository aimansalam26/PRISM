import unittest,json,tempfile,sqlite3
from app import KO,check
from graph_store import GraphStore,fingerprint
import review_tools as rt
import edge_proposals as ep
import candidates
import test_coverage_pipeline as base

class ReviewTests(unittest.TestCase):
 setUp=base.CoverageTests.setUp
 tearDown=base.CoverageTests.tearDown
 ko=base.CoverageTests.ko
 fake=base.CoverageTests.fake
 run_extract=base.CoverageTests.run_extract
 def test_frontmatter_is_evidence_not_rule(self):
  from coverage_pipeline import source_units
  data=b'---\ntitle: Netherlands benefits\n---\nBody'
  ss=rt.add_document_context(data,[self.s]);self.assertTrue(ss[-1]['context_only'])
  self.assertEqual(ss[-1]['line_end'],3)
  self.assertEqual(source_units(ss)[-1]['kind'],'structure')
  self.assertTrue(any(r['quote']=='title: Netherlands benefits' for r in rt.context_options(self.s,ss)))
 def test_context_exact_evidence(self):
  k=self.ko(self.units[2]);k['context_evidence']=[{'section_id':'S','quote':'Leave Entitlement','purpose':'subject'}]
  self.assertEqual(check(k,{'S':self.s}),[])
  k['context_evidence'][0]['quote']='Made up subject'
  self.assertTrue(check(k,{'S':self.s}))
 def test_coverage_stale_after_ko_edit(self):
  self.run_extract(self.fake());ks=[json.loads(r[0]) for r in self.db.execute('SELECT body FROM state')]
  u=next(u for u in rt.unit_state(self.db,self.units,ks) if u['kind']=='bullet')
  rt.review_unit(self.db,self.units,ks,dict(u,decision='complete',expected_rule_count=1,note='Every independent rule checked'),'human')
  self.assertTrue(next(x for x in rt.unit_state(self.db,self.units,ks) if x['unit_id']==u['unit_id'])['review_current'])
  ks[0]['summary']='Edited meaning'
  self.assertFalse(next(x for x in rt.unit_state(self.db,self.units,ks) if x['unit_id']==u['unit_id'])['review_current'])
 def test_rerun_stages_instead_of_graph_duplicates(self):
  self.run_extract(self.fake());client=self.fake();original=client.extract
  def changed(*args):
   r=json.loads(original(*args))
   for k in r['kos']:k['summary']='Revised '+k['summary']
   return json.dumps(r)
  client.extract=changed;result=self.run_extract(client)
  self.assertEqual(result['staged_comparisons'],5)
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM state').fetchone()[0],5)
  proposal=rt.comparisons(self.db)[0]
  rt.resolve_comparison(self.db,{'id':proposal['id'],'action':'replace','note':'Revised interpretation checked','replace_ids':[proposal['existing'][0]['id']]},'human',check,{'S':self.s})
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM state').fetchone()[0],6)
  old=json.loads(self.db.execute('SELECT body FROM state WHERE id=?',(proposal['existing'][0]['id'],)).fetchone()[0]);self.assertEqual(old['status'],'rejected')
 def test_cannot_complete_more_rules_than_linked_kos(self):
  self.run_extract(self.fake());ks=[json.loads(r[0]) for r in self.db.execute('SELECT body FROM state')]
  u=next(u for u in rt.unit_state(self.db,self.units,ks) if u['kind']=='bullet')
  with self.assertRaises(ValueError):rt.review_unit(self.db,self.units,ks,dict(u,decision='complete',expected_rule_count=2,note='Two independent clauses'),'human')
 def test_group_edit_is_collective(self):
  self.run_extract(self.fake());rows=[json.loads(r[0]) for r in self.db.execute('SELECT body FROM state')][:2]
  for k in rows:k.update(requirement_group_id='REQ',logical_operator='UNCERTAIN',status='approved');self.db.execute('UPDATE state SET body=? WHERE id=?',(json.dumps(k),k['id']))
  self.db.commit();rt.group_update(self.db,{'group_id':'REQ','logical_operator':'AND','note':'Source requires both criteria','fingerprint':fingerprint(rows)},'human')
  result=[json.loads(r[0]) for r in self.db.execute('SELECT body FROM state') if json.loads(r[0]).get('requirement_group_id')=='REQ']
  self.assertTrue(all(k['logical_operator']=='AND' and k['status']=='proposed' for k in result))

class EdgeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.graph=GraphStore(self.tmp.name)
  self.nodes=[{'key':k,'project':'p','fingerprint':k,'errors':[],'source_file':'/handbook/p.md','ko':{'status':'approved','summary':k,'source_quote':'Amount is 150.','watched_fields':['medical_allowance']},'section':{'heading_path':['Medical'],'raw_text':'Amount is 150.','outgoing_links':[]}} for k in ['a','b']]
  self.graph.state=lambda:{'nodes':self.nodes,'edges':[],'warnings':[]}
 def tearDown(self):self.graph.db.close();self.tmp.cleanup()
 def reply(self,decision='relationship'):
  return {'decision':decision,'direction':'a_to_b' if decision=='relationship' else 'none','relation_type':'DEPENDS_ON' if decision=='relationship' else None,'justification':'Test evidence rationale','field_mappings':[{'source_field':'medical_allowance','target_field':'medical_allowance'}] if decision=='relationship' else [],'dimension_mapping':[],'evidence':[{'node':k,'quote':'Amount is 150.'} for k in ['a','b']],'scope_notes':'Unknown dates'}
 def client(self,p):
  class Fake:
   def extract(self,*a):return json.dumps(p)
  return Fake()
 def test_model_checkpoint_and_no_edges(self):
  s=ep.generate(self.graph,self.client(self.reply()),{'name':'mock','provider':'mock'},1,lambda _:None)
  self.assertEqual(s['saved'],1);self.assertEqual(self.graph.db.execute('SELECT COUNT(*) FROM edges').fetchone()[0],0)
  self.assertEqual(len(ep.graph_state(self.graph)['ai_suggestions']),1)
  s=ep.generate(self.graph,self.client(self.reply()),{'name':'mock','provider':'mock'},1,lambda _:None);self.assertEqual(s['saved'],0)
 def test_bad_evidence_rejected(self):
  r=candidates.report(self.graph)['candidates'][0];p=self.reply();p['evidence'][0]['quote']='Invented'
  with self.assertRaises(ValueError):ep.validate(p,r,{n['key']:n for n in self.nodes})
 def test_negative_review_and_stale(self):
  ep.generate(self.graph,self.client(self.reply('no_dependency')),{'name':'mock','provider':'mock'},1,lambda _:None)
  v=next(iter(ep.saved(self.graph).values()))
  p={'id':v['id'],'proposal_fingerprint':fingerprint(v),'action':'accept','note':'No causal evidence'}
  self.nodes[0]['fingerprint']='changed'
  with self.assertRaises(ValueError):ep.review(self.graph,p,'human')
  self.nodes[0]['fingerprint']='a';ep.review(self.graph,p,'human')
  self.assertEqual(candidates.report(self.graph)['candidates'][0]['status'],'no_dependency')
 def test_fragment_and_lexical_retrieval(self):
  a,b=self.nodes;a['project']='a';b['project']='b';b['source_file']='/handbook/b.md';a['ko']['watched_fields']=[];b['ko']['watched_fields']=[];a['section']['outgoing_links']=[{'target_url':'/handbook/b/#medical'}]
  self.assertEqual(len(candidates.generate(self.nodes)),1)
  a['section']['outgoing_links']=[{'target_url':'/handbook/b/#missing'}];notes=[];self.assertEqual(candidates.generate(self.nodes,notes),[]);self.assertTrue(notes)
  a['section']['outgoing_links']=[];a['ko']['watched_fields']=['bike_purchase_cap_eur'];b['ko']['watched_fields']=['bicycle_limit_eur'];self.assertEqual(len(candidates.generate(self.nodes)),1)
if __name__=='__main__':unittest.main()
