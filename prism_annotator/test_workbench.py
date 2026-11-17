import json, tempfile, unittest
from pathlib import Path
from app import check,render
from parser import parse_file
class Tests(unittest.TestCase):
 def test_exact_spans_and_quote(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'p.md';p.write_bytes(b'# Benefits\r\n\r\nAmount is EUR 150.\r\n\r\n<details>\r\n<summary>Coverage</summary>\r\n\r\nProrated.\r\n</details>\r\n')
   ss,w=parse_file(p,'T');lookup={s['section_id']:s for s in ss}
   for s in ss:self.assertEqual(s['raw_text'],''.join(p.read_bytes().decode().splitlines(keepends=True)[s['line_start']-1:s['line_end']]))
   s=ss[0];k=dict(section_id=s['section_id'],summary='Amount',source_quote='Amount is EUR 150.',watched_fields=['amount'],applicability_tuples=[dict(employment_types=['unknown'],org_roles=['unknown'],entities=['unknown'],jurisdictions=['unknown'],temporal_window=['unknown','unknown'])],scope_evidence='',additional_conditions=[])
   self.assertEqual(check(k,lookup),[])
   k['source_quote']='Amount is EUR 200.';self.assertTrue(check(k,lookup))
 def test_preview_sanitized(self):
  html=render('<script>alert(1)</script><a href="javascript:alert(1)">bad</a>')
  self.assertNotIn('<script',html);self.assertNotIn('href="javascript:',html)
if __name__=='__main__':unittest.main()
