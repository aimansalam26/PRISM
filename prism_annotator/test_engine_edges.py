import unittest
import test_graph as base
from graph_store import unknown_scope
class EdgeEngineMetadataTests(unittest.TestCase):
 setUp=base.GraphTests.setUp
 tearDown=base.GraphTests.tearDown
 def test_new_metadata_persisted_and_country_canonicalised(self):
  e=base.GraphTests.edge(self);scope=unknown_scope();scope['jurisdictions']=['Netherlands'];e.update(certainty='confirmed',applicability_tuples=[scope],scope_notes='Synthetic fixture: Netherlands context')
  saved=self.g.save_edge(e,'Reviewer');self.assertEqual(saved['certainty'],'confirmed');self.assertEqual(saved['applicability_tuples'][0]['jurisdictions'],['NL'])
 def test_implicit_edge_scope_and_certainty_remain_unknown(self):
  e=self.g.save_edge(base.GraphTests.edge(self),'R');self.assertEqual(e['certainty'],'uncertain');self.assertEqual(e['applicability_tuples'][0]['temporal_window'],['unknown','unknown'])
 def test_override_needs_independence_and_trigger(self):
  e=base.GraphTests.edge(self,'OVERRIDES');e.update(field_mappings=[],trigger_fields=['amount'])
  with self.assertRaisesRegex(ValueError,'independent'):self.g.save_edge(e,'R')
  e['override_mode']='independent_value';self.g.save_edge(e,'R')
if __name__=='__main__':unittest.main()
