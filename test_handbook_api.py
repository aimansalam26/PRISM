import json,unittest,tempfile
from pathlib import Path
import app
from build_handbook_scenario import build
from test_handbook_bridge import packet,event
from ui_exports import export_report,report_sheets
from run_suite import load_suite
class HandbookAPITests(unittest.TestCase):
 def test_upload_reference_and_exports(self):
  scenario=build(packet(),event());run=app.analyse(scenario)
  self.assertTrue(run['payload']['reference_checks']['HB-TEST']['matches'])
  self.assertEqual(run['payload']['results']['HB-TEST']['prism']['items'][0]['status'],'Defer')
  for kind in ['csv','xlsx','markdown','results','corpus','session']:
   content,mime,name=export_report(run,{},kind);self.assertTrue(content);self.assertTrue(name)
  session=json.loads(export_report(run,{},'session')[0]);self.assertEqual(app.analyse(session)['payload'],run['payload'])
 def test_cli_and_ui_hash_the_same_single_scenario(self):
  scenario=build(packet(),event())
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'scenario.json';p.write_text(json.dumps(scenario));self.assertEqual(load_suite(p),app.normalise_input(scenario)[0])
 def test_known_new_dimensions_in_spreadsheet_export(self):
  from test_handbook_engine import handbook
  s=handbook();s['title']='Synthetic known-scope fixture';run=app.analyse(s);rows=report_sheets(run,{})['Affected scopes'];self.assertIn('Employment types',rows[0]);self.assertGreater(len(rows),1)
if __name__=='__main__':unittest.main()
