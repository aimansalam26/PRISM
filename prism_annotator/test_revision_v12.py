import copy,json,shutil,unittest
from unittest.mock import patch
from pathlib import Path
from app import check
from node_actions import NodeActions
import test_light_review as light
import engine_compatibility
import test_graph as graphs
from import_kos import preview
import test_import_actions as imports

class CandidateEditing(unittest.TestCase):
 setUp=light.FinalTests.setUp
 tearDown=light.FinalTests.tearDown
 def test_cross_project_context_edit_and_audit(self):
  other=self.root/'other';shutil.copytree(self.p,other)
  actions=NodeActions(self.graph,check);ctx=actions.context('other::K1');self.assertEqual(ctx['ko']['id'],'K1')
  result=actions.edit({'key':'other::K1','fingerprint':ctx['fingerprint'],'scope_evidence':'Reviewed local context','decision':'approved'},'Researcher')
  self.assertEqual(result['status'],'approved');self.assertEqual(result['curation_review']['origin'],'candidate_review')
  self.assertNotIn('curation_review',actions.context('pilot::K1')['ko'])
  with self.assertRaisesRegex(ValueError,'changed'):actions.edit({'key':'other::K1','fingerprint':ctx['fingerprint']},'R')
 def test_unsupported_scope_can_be_saved_but_not_approved(self):
  actions=NodeActions(self.graph,check);ctx=actions.context('pilot::K1');tuples=copy.deepcopy(self.k['applicability_tuples']);tuples[0]['jurisdictions']=['NL']
  payload={'key':'pilot::K1','fingerprint':ctx['fingerprint'],'applicability_tuples':tuples,'decision':'approved'}
  with self.assertRaisesRegex(ValueError,'jurisdictions=NL'):actions.edit(payload,'R')
  payload['decision']='proposed';self.assertEqual(actions.edit(payload,'R')['status'],'proposed')
 def test_compatibility_is_not_an_engine_export(self):
  report=engine_compatibility.report(self.graph);self.assertFalse(report['engine_ready']);self.assertTrue(any(i['code']=='scope_unresolved' for i in report['issues']))
 def test_existing_edges_go_stale_after_scope_edit(self):
  other=self.root/'other';shutil.copytree(self.p,other)
  self.graph.save_edge({'source':'pilot::K1','target':'other::K1','relation_type':'REVIEW_ONLY','trigger_fields':['leave_days'],'status':'approved','justification':'Fixture','field_mappings':[],'dimension_mapping':[]},'R')
  actions=NodeActions(self.graph,check);ctx=actions.context('other::K1');actions.edit({'key':'other::K1','fingerprint':ctx['fingerprint'],'decision':'proposed'},'R')
  self.assertTrue(self.graph.state()['edges'][0]['stale'])

class AdoptionChecks(unittest.TestCase):
 setUp=graphs.GraphTests.setUp
 tearDown=graphs.GraphTests.tearDown
 def test_dates_cannot_be_adopted(self):
  e=self.edge('ADOPTS_VALUE') if hasattr(self,'edge') else graphs.GraphTests.edge(self,'ADOPTS_VALUE');e['dimension_mapping']=[{'dimension':'temporal_window','from':['2026-01-01'],'to':['2027-01-01']}]
  with self.assertRaisesRegex(ValueError,'dates'):self.g.save_edge(e,'R')
 def test_unknown_cannot_be_rewritten(self):
  e=graphs.GraphTests.edge(self,'ADOPTS_VALUE');e['dimension_mapping']=[{'dimension':'jurisdictions','from':['unknown'],'to':['NL']}]
  with self.assertRaisesRegex(ValueError,'known'):self.g.save_edge(e,'R')

class ImportScopeChecks(unittest.TestCase):
 setUp=imports.ImportTests.setUp
 tearDown=imports.ImportTests.tearDown
 def test_unsupported_import_downgrades_prior_approval(self):
  self.raw['applicability_tuples'][0]['jurisdictions']=['NL'];p=preview([self.raw],[self.section],{},check);self.assertFalse(p['items'][0]['can_preserve_approval'])

if __name__=='__main__':unittest.main()
