import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cli
class CLITests(unittest.TestCase):
 def test_search_and_new_project(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);source=root/'content/handbook/benefits/netherlands.md';source.parent.mkdir(parents=True);source.write_text('# Benefits')
   c={'handbook_root':td,'projects_dir':str(root/'projects')}
   with patch('builtins.input',side_effect=['1','netherlands','1','nl-pilot']),patch('cli.launch') as launch:
    cli.new_project(c)
    launch.assert_called_once_with(source,root/'projects/nl-pilot')
 def test_resume(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);source=root/'source.md';source.write_text('text');proj=root/'projects/pilot';proj.mkdir(parents=True);(proj/'manifest.json').write_text(json.dumps({'source_file':str(source)}))
   c={'projects_dir':str(root/'projects')}
   with patch('builtins.input',return_value='1'),patch('cli.launch') as launch:
    cli.reopen(c);launch.assert_called_once_with(source,proj)
 def test_no_overwrite(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'existing';p.mkdir()
   with patch('cli.select_source',return_value=root/'source.md'),patch('builtins.input',return_value='existing'):
    with self.assertRaises(ValueError):cli.new_project({'projects_dir':td})
 def test_settings_persistence(self):
  with tempfile.TemporaryDirectory() as td:
   with patch('cli.CONFIG_DIR',Path(td)),patch('cli.CONFIG_FILE',Path(td)/'settings.json'):
    c={'handbook_root':'example','projects_dir':'projects'};cli.save_config(c);self.assertEqual(cli.read_config(),c)
if __name__=='__main__':unittest.main()
