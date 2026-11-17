"""Run self-contained regression checks; original corpus/workbook checks need your data."""
import subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
commands=[
 [sys.executable,'-c',"import unittest,test_engine; suite=unittest.TestSuite(); skip={'test_all_seven_reference_comparisons','test_blank_workbook_is_not_gold'}; [suite.addTest(t) for group in unittest.defaultTestLoader.loadTestsFromModule(test_engine) for t in group if t._testMethodName not in skip]; result=unittest.TextTestRunner(verbosity=1).run(suite); raise SystemExit(not result.wasSuccessful())"],
 [sys.executable,'-m','unittest','test_handbook_engine','test_handbook_bridge','test_handbook_api'],
 [sys.executable,'-m','unittest','discover','-s','prism_annotator','-p','test_*.py'],
 [sys.executable,'smoke_handbook_bridge.py']]
for cmd in commands:
 subprocess.run(cmd,cwd=root,check=True)
print('Self-contained checks passed. Original scenario/workbook-dependent tests and original UI suite were NOT included; run them separately with your data.')
