import json,sqlite3,tempfile,unittest
from pathlib import Path
from app import check
from import_kos import preview,apply
from node_actions import NodeActions
from graph_store import GraphStore,fingerprint
import test_graph

class ImportTests(unittest.TestCase):
 def setUp(self):
  self.section={'section_id':'NEW','raw_text':'Employees receive 100 EUR.','line_start':1,'line_end':1,'heading_path':['Benefits'],'disclosure_title':None,'source_file':'test.md','source_sha256':'hash'}
  self.raw={'ko_id':'OLD_1','annotation_status':'verified','provenance':{'source_sha256':'hash','section_id':'OLD','source_file':'test.md'},'evidence':{'source_quote':'Employees receive 100 EUR.'},'semantics':{'summary':'Allowance','watched_fields':['amount']},'applicability_tuples':[{'employment_types':['unknown'],'org_roles':['unknown'],'entities':['unknown'],'jurisdictions':['unknown'],'temporal_window':['unknown','unknown']}],'scope_evidence':'unknown','additional_conditions':[]}
  self.db=sqlite3.connect(':memory:');self.db.execute('CREATE TABLE state(id TEXT PRIMARY KEY,body TEXT)');self.db.execute('CREATE TABLE audit(time REAL,reviewer TEXT,id TEXT,before TEXT,after TEXT)')
 def tearDown(self):self.db.close()
 def test_original_format_remaps_and_retains_prior_approval(self):
  p=preview([self.raw],[self.section],{},check);self.assertEqual(p['counts']['import'],1);self.assertEqual(p['items'][0]['ko']['section_id'],'NEW');apply(self.db,p,'reviewer',True);k=json.loads(self.db.execute('SELECT body FROM state').fetchone()[0]);self.assertEqual(k['status'],'approved');self.assertEqual(k['import_metadata']['original_status'],'verified')
 def test_wrong_source_and_conflicting_id_blocked(self):
  bad=dict(self.raw,provenance={'source_sha256':'other'});self.assertEqual(preview([bad],[self.section],{},check)['counts']['blocked'],1)
  p=preview([self.raw],[self.section],{'OLD_1':{'summary':'other'}},check);self.assertEqual(p['counts']['blocked'],1)
 def test_no_hash_cannot_preserve_approval(self):
  self.raw['provenance']={};p=preview([self.raw],[self.section],{},check);self.assertFalse(p['items'][0]['can_preserve_approval']);apply(self.db,p,'r',True);self.assertEqual(json.loads(self.db.execute('SELECT body FROM state').fetchone()[0])['status'],'proposed')
 def test_idempotent_import_and_duplicate_input(self):
  p=preview([self.raw],[self.section],{},check);apply(self.db,p,'r',False);k=json.loads(self.db.execute('SELECT body FROM state').fetchone()[0]);self.assertEqual(preview([self.raw],[self.section],{k['id']:k},check)['counts']['skip'],1);self.assertEqual(preview([self.raw,self.raw],[self.section],{},check)['counts']['blocked'],1)

class ActionTests(unittest.TestCase):
 def setUp(self):
  self.fixture=test_graph.GraphTests();self.fixture.setUp();self.g=self.fixture.g;self.actions=NodeActions(self.g,lambda k,s:[])
 def tearDown(self):self.fixture.tearDown()
 def test_two_step_delete_restore_and_edge_stale(self):
  self.g.save_edge(self.fixture.edge(),'r');p=self.actions.prepare_delete('nl::KO_1');self.assertEqual(p['connected_edges'],1)
  with self.assertRaises(ValueError):self.actions.delete({'confirmation_token':p['confirmation_token'],'typed_id':'wrong'},'r')
  self.assertEqual(len(self.g.state()['nodes']),2)
  p=self.actions.prepare_delete('nl::KO_1');self.actions.delete({'confirmation_token':p['confirmation_token'],'typed_id':'KO_1'},'r');state=self.g.state();self.assertEqual(len(state['nodes']),1);self.assertEqual(len(state['trash']),1);self.assertTrue(state['edges'][0]['stale']);self.assertEqual(self.g.export()['approved_edges'],[])
  with self.assertRaises(ValueError):self.actions.delete({'confirmation_token':p['confirmation_token'],'typed_id':'KO_1'},'r')
  self.actions.restore('nl::KO_1','r');self.assertEqual(len(self.g.state()['nodes']),2);self.assertEqual(self.g.state()['nodes'][0]['ko']['status'],'proposed')
 def test_concurrent_edits_block_delete_and_edit(self):
  p=self.actions.prepare_delete('nl::KO_1');n=self.g.state()['nodes'][0];self.actions.edit({'key':n['key'],'fingerprint':n['fingerprint'],'summary':'Changed'},'r')
  with self.assertRaises(ValueError):self.actions.delete({'confirmation_token':p['confirmation_token'],'typed_id':'KO_1'},'r')
  with self.assertRaises(ValueError):self.actions.edit({'key':n['key'],'fingerprint':n['fingerprint'],'summary':'Old edit'},'r')
 def test_path_traversal_rejected(self):
  with self.assertRaises(ValueError):self.actions.prepare_delete('../nl::KO_1')
if __name__=='__main__':unittest.main()
