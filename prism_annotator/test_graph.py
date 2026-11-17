import json,sqlite3,tempfile,unittest
from pathlib import Path
from graph_store import GraphStore
class GraphTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  for name in ['nl','uk']:
   p=self.root/name;p.mkdir();(p/'manifest.json').write_text(json.dumps({'source_file':name+'.md','source_sha256':'sha-'+name}));(p/'parsed_sections.json').write_text(json.dumps([{'section_id':'S','raw_text':'Allowance 100','line_start':1}]))
   k={'id':'KO_1','section_id':'S','summary':'Allowance','source_quote':'Allowance 100','status':'approved','watched_fields':['amount'],'applicability_tuples':[{'jurisdictions':['unknown']}],'validation_errors':[]}
   c=sqlite3.connect(p/'annotations.sqlite');c.execute('CREATE TABLE state(id TEXT PRIMARY KEY,body TEXT)');c.execute('INSERT INTO state VALUES (?,?)',('KO_1',json.dumps(k)));c.commit();c.close()
  self.g=GraphStore(self.root)
 def tearDown(self):self.g.db.close();self.tmp.cleanup()
 def edge(self,typ='DEPENDS_ON'):
  return dict(source='nl::KO_1',target='uk::KO_1',relation_type=typ,status='approved',justification='Test relationship evidence',field_mappings=[{'source_field':'amount','target_field':'amount'}],dimension_mapping=[])
 def test_cross_file_and_export(self):
  e=self.g.save_edge(self.edge(),'tester');s=self.g.export();self.assertEqual(len(s['nodes']),2);self.assertEqual(len(s['approved_edges']),1);self.assertEqual(len(s['audit']),1);self.assertTrue(s['edges'][0]['scope_incomplete']);self.assertEqual(e['evidence'][0]['source_file'],'nl.md')
 def test_stale_on_edit(self):
  self.g.save_edge(self.edge(),'tester');c=sqlite3.connect(self.root/'nl/annotations.sqlite');k=json.loads(c.execute('SELECT body FROM state').fetchone()[0]);k['summary']='Revised';c.execute('UPDATE state SET body=?',(json.dumps(k),));c.commit();c.close();s=self.g.export();self.assertTrue(s['edges'][0]['stale']);self.assertEqual(s['approved_edges'],[])
 def test_no_self_or_invalid_fields(self):
  e=self.edge();e['target']=e['source']
  with self.assertRaises(ValueError):self.g.save_edge(e,'t')
  e=self.edge();e['field_mappings'][0]['target_field']='invented'
  with self.assertRaises(ValueError):self.g.save_edge(e,'t')
 def test_terminal(self):
  e=self.edge('REVIEW_ONLY')
  with self.assertRaises(ValueError):self.g.save_edge(e,'t')
  e['field_mappings']=[];self.g.save_edge(e,'t')
 def test_adoption(self):
  e=self.edge('ADOPTS_VALUE')
  with self.assertRaises(ValueError):self.g.save_edge(e,'t')
  e['dimension_mapping']=[{'dimension':'jurisdictions','from':['NL'],'to':['UK']}];self.g.save_edge(e,'t')
 def test_duplicate_and_position(self):
  self.g.save_edge(self.edge(),'t')
  with self.assertRaises(ValueError):self.g.save_edge(self.edge(),'t')
  self.g.save_position({'key':'nl::KO_1','x':20,'y':30});self.assertEqual(self.g.state()['positions']['nl::KO_1']['x'],20)
if __name__=='__main__':unittest.main()
