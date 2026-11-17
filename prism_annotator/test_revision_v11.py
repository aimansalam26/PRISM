import copy,tempfile,unittest
from unittest.mock import patch,MagicMock
from pathlib import Path
import scope_grounding as sg
from ollama_backend import Ollama

class ScopeRepair(unittest.TestCase):
 def setUp(self):
  self.sections={'S':{'raw_text':'Full-time Netherlands team members receive EUR 150.'}}
  self.k={'section_id':'S','source_quote':self.sections['S']['raw_text'],'scope_support':[], 'applicability_tuples':[{'employment_types':['full_time'],'org_roles':['unknown'],'entities':['unknown'],'jurisdictions':['netherlands'],'temporal_window':['unknown','unknown']}]}
 def test_alias_and_citation_repair(self):
  x=sg.reconcile(self.k,self.sections)
  self.assertEqual(x['applicability_tuples'][0]['jurisdictions'],['NL'])
  self.assertFalse(any(r['status']=='unsupported' for r in sg.report(x,self.sections)))
  self.assertEqual(self.k['applicability_tuples'][0]['jurisdictions'],['netherlands'])
 def test_edited_value_replaces_stale_hidden_citation(self):
  x=sg.reconcile(self.k,self.sections);x['scope_support'][0]['value']='stale'
  x=sg.reconcile(x,self.sections)
  self.assertFalse(any(r['value']=='stale' for r in x['scope_support']))
  self.assertTrue(sg.evidence_for(x,self.sections,0,'employment_types','full_time'))
 def test_wrong_dimension_is_not_cleared_on_save(self):
  self.k['applicability_tuples'][0]['entities']=['netherlands'];self.k['applicability_tuples'][0]['org_roles']=['team_members']
  x=sg.reconcile(self.k,self.sections);bad=[r for r in sg.report(x,self.sections) if r['status']=='unsupported']
  self.assertEqual({r['dimension'] for r in bad},{'entities','org_roles'})
  self.assertTrue(all(r['reason'] for r in bad));self.assertEqual(x['applicability_tuples'][0]['entities'],['netherlands'])
 def test_unknown_is_not_engine_ready_or_fabricated_date(self):
  x=sg.reconcile(self.k,self.sections);r=sg.scope_readiness(x,self.sections)
  self.assertEqual(r['status'],'scope_unresolved');self.assertFalse(r['engine_ready'])
  self.assertEqual(x['applicability_tuples'][0]['temporal_window'],['unknown','unknown'])
 def test_other_tuple_and_forged_context_not_inherited(self):
  self.k['applicability_tuples'].append(copy.deepcopy(self.k['applicability_tuples'][0]));self.k['applicability_tuples'][1]['jurisdictions']=['UK']
  x=sg.reconcile(self.k,self.sections);self.assertIsNone(sg.evidence_for(x,self.sections,1,'jurisdictions','UK'))
  self.assertEqual(x['applicability_tuples'][1]['jurisdictions'],['UK'])

class ServerStartup(unittest.TestCase):
 def test_running_reused(self):
  c=Ollama()
  with patch.object(c,'request',return_value={'models':[]}),patch('ollama_backend.subprocess.Popen') as launch:
   self.assertFalse(c.ensure_running());launch.assert_not_called()
 def test_missing_install_actionable(self):
  c=Ollama()
  with patch.object(c,'request',side_effect=RuntimeError('Connection refused')),patch('ollama_backend.shutil.which',return_value=None):
   with self.assertRaisesRegex(RuntimeError,'not installed'):c.ensure_running()
 def test_starts_local_background_once(self):
  c=Ollama()
  with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'LOCALAPPDATA':d}),patch.object(c,'request',side_effect=[RuntimeError('WinError 10061 actively refused'),{'models':[]}]),patch('ollama_backend.shutil.which',return_value='/bin/ollama'),patch('ollama_backend.subprocess.Popen') as launch:
   self.assertTrue(c.ensure_running());self.assertEqual(launch.call_args.args[0],['/bin/ollama','serve']);self.assertEqual(launch.call_args.kwargs['env']['OLLAMA_HOST'],'127.0.0.1:11434');self.assertNotIn('shell',launch.call_args.kwargs)
 def test_bad_or_busy_service_is_not_restarted(self):
  for result in [RuntimeError('generation timed out'),RuntimeError('Ollama HTTP 404')]:
   c=Ollama()
   with patch.object(c,'request',side_effect=result),patch('ollama_backend.subprocess.Popen') as launch:
    with self.assertRaises(RuntimeError):c.ensure_running()
    launch.assert_not_called()
 def test_server_exit_returns_log_path(self):
  c=Ollama();child=MagicMock();child.poll.return_value=1
  with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'LOCALAPPDATA':d}),patch.object(c,'request',side_effect=RuntimeError('Connection refused')),patch('ollama_backend.shutil.which',return_value='/bin/ollama'),patch('ollama_backend.subprocess.Popen',return_value=child):
   with self.assertRaisesRegex(RuntimeError,'ollama-server.log'):c.ensure_running()
if __name__=='__main__':unittest.main()
