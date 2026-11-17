import unittest,tempfile
from pathlib import Path
from candidates import generate,page_path,report,review
from graph_store import GraphStore
from handbook_context import context_for

class CandidatesTests(unittest.TestCase):
 def node(self,key,project='a',heading=None,fields=None,links=None):
  return {'key':key,'project':project,'fingerprint':key,'errors':[], 'source_file':'/repo/content/handbook/'+project+'.md','ko':{'status':'proposed','watched_fields':fields or []},'section':{'heading_path':heading or ['Benefits','Medical'],'outgoing_links':links or []}}
 def test_unordered_and_cross_document_fields(self):
  ns=[self.node('a1',fields=['medical_allowance']),self.node('a2'),self.node('b1','b',fields=['medical_allowance'])]
  rows=generate(ns);self.assertEqual(len(rows),2)
  self.assertEqual({(r['a'],r['b']) for r in rows},{('a1','a2'),('a1','b1')})
  self.assertEqual(rows,generate(list(reversed(ns))))
 def test_same_generic_heading_does_not_link_documents(self):
  self.assertFalse(generate([self.node('a'),self.node('b','b')]))
 def test_document_links_nominate_without_direction(self):
  rows=generate([self.node('a',links=[{'target_url':'/handbook/b/'}]),self.node('b','b')])
  self.assertEqual(len(rows),1);self.assertNotIn('relation_type',rows[0])
 def test_rejected_and_invalid_excluded(self):
  a=self.node('a');b=self.node('b');b['ko']['status']='rejected'
  self.assertFalse(generate([a,b]));b['ko']['status']='approved';b['errors']=['bad quote'];self.assertFalse(generate([a,b]))
 def test_review_stale_and_audit(self):
  with tempfile.TemporaryDirectory() as d:
   graph=GraphStore(d);nodes=[self.node('a'),self.node('b')]
   graph.state=lambda:{'nodes':nodes,'edges':[],'warnings':[]}
   r=report(graph)['candidates'][0]
   review(graph,dict(r,decision='no_dependency',note='Independent amounts'), 'human')
   self.assertEqual(report(graph)['candidates'][0]['status'],'no_dependency')
   nodes[0]['fingerprint']='changed'
   self.assertTrue(report(graph)['candidates'][0]['stale_review'])
   with self.assertRaises(ValueError):review(graph,dict(r,decision='no_dependency',note='old'), 'human')
   self.assertEqual(graph.db.execute('SELECT COUNT(*) FROM audit').fetchone()[0],1);graph.db.close()
 def test_path_and_hint(self):
  self.assertEqual(page_path(r'C:\repo\content\handbook\benefits\_index.md'),'/handbook/benefits')
  self.assertEqual(context_for({'heading_path':['Medical Allowance'],'disclosure_title':'Eligibility Requirements'})['heading_hint'],'eligibility')
if __name__=='__main__':unittest.main()
