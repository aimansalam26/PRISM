import json,sqlite3,unittest
from app import KO,check
from coverage_pipeline import source_units,init_db,execute,report,review_section,heading_only

TEXT='''<details markdown="1">\r
<summary>Leave Entitlement</summary>\r
\r
* Minimum 20 vacation days annually\r
* Accrue at 1.67 days/month from start date\r
* Unused days carry over to the next calendar year but expire July 1st\r
* Pro-rated for partial years\r
\r
</details>\r
'''
class CoverageTests(unittest.TestCase):
 def setUp(self):
  self.s={'section_id':'S','raw_text':TEXT,'line_start':1,'line_end':9,'heading_path':['Benefits'],'disclosure_title':'Leave Entitlement','source_file':'nl.md','source_sha256':'abc'}
  self.units=source_units([self.s]);self.db=sqlite3.connect(':memory:');self.db.execute('CREATE TABLE state(id TEXT PRIMARY KEY,body TEXT)');self.db.execute('CREATE TABLE audit(time REAL,reviewer TEXT,id TEXT,before TEXT,after TEXT)');init_db(self.db)
  self.selected={'provider':'mock','name':'test'}
 def tearDown(self):self.db.close()
 def ko(self,u,summary=None):
  return {'section_id':'S','summary':summary or u['raw_text'].strip(),'source_quote':u['raw_text'].strip(),'watched_fields':['value'],'applicability_tuples':[{'employment_types':['unknown'],'org_roles':['unknown'],'entities':['unknown'],'jurisdictions':['unknown'],'temporal_window':['unknown','unknown']}],'scope_evidence':'Unknown','additional_conditions':[]}
 def fake(self,fail=False):
  outer=self
  class Client:
   def __init__(self):self.calls=[]
   def extract(self,model,prompt,payload,schema):
    u=payload['target'];self.calls.append(u)
    if fail and 'Minimum' in u['raw_text']:raise RuntimeError('truncated')
    ks=[outer.ko(u)]
    if 'carry over' in u['raw_text']:ks=[outer.ko(u,'Carry-over permission'),outer.ko(u,'Expiry on July 1')]
    return json.dumps({'unit_id':u['unit_id'],'decision':'rule','reason':'Rule-bearing bullet','kos':ks})
  return Client()
 def run_extract(self,c,mode='all'):
  return execute(self.db,self.units,[self.s],c,self.selected,KO,check,mode,lambda x:None)
 def test_inventory_exact_and_five_mocked_rules(self):
  bullets=[u for u in self.units if u['kind']=='bullet'];self.assertEqual(len(bullets),4)
  lines=TEXT.splitlines(keepends=True)
  for u in self.units:self.assertEqual(u['raw_text'],''.join(lines[u['line_start']-1:u['line_end']]))
  c=self.fake();s=self.run_extract(c);self.assertEqual(len(c.calls),4);self.assertEqual(s['new_kos'],5)
  self.assertEqual(report(self.db,self.units,[self.s])['sections'][0]['linked_units'],4)
 def test_failure_continues_and_resume(self):
  s=self.run_extract(self.fake(True));self.assertEqual(s['failed'],1);self.assertEqual(s['completed'],3)
  c=self.fake();self.run_extract(c,'pending');self.assertEqual(len(c.calls),1)
 def test_full_rerun_preserves_human_records(self):
  self.run_extract(self.fake());row=self.db.execute('SELECT id,body FROM state LIMIT 1').fetchone();k=json.loads(row[1]);k.update(status='approved',note='human decision');self.db.execute('UPDATE state SET body=? WHERE id=?',(json.dumps(k),row[0]));self.db.commit()
  s=self.run_extract(self.fake());self.assertEqual(s['new_kos'],0);self.assertEqual(json.loads(self.db.execute('SELECT body FROM state WHERE id=?',(row[0],)).fetchone()[0])['note'],'human decision')
 def test_human_review_invalidated_by_rerun(self):
  self.run_extract(self.fake());review_section(self.db,self.units,[self.s],{'section_id':'S','note':'Checked all clauses'},'reviewer');self.assertTrue(report(self.db,self.units,[self.s])['sections'][0]['review_current']);self.run_extract(self.fake());self.assertFalse(report(self.db,self.units,[self.s])['sections'][0]['review_current'])
 def test_retry_coverage_does_not_treat_one_approved_ko_as_complete(self):
  self.run_extract(self.fake());c=self.fake();self.run_extract(c,'uncovered');self.assertEqual(len(c.calls),4)
  review_section(self.db,self.units,[self.s],{'section_id':'S','note':'All clauses checked'},'r');c=self.fake();self.run_extract(c,'uncovered');self.assertEqual(len(c.calls),0)
 def test_heading_flag(self):
  self.assertTrue(heading_only('Leave Entitlement',self.s));self.assertFalse(heading_only('Accrue at 1.67 days/month',self.s))
 def test_missing_decision_not_checkpointed(self):
  class Bad:
   def extract(self,*a):return '{"kos":[]}'
  s=self.run_extract(Bad());self.assertEqual(s['failed'],4);self.assertEqual(s['completed'],0)
 def test_explicit_nonrule(self):
  class Negative:
   def extract(self,m,p,payload,s):return json.dumps({'unit_id':payload['target']['unit_id'],'decision':'not_a_rule','reason':'Test negative, human review required','kos':[]})
  self.run_extract(Negative());r=report(self.db,self.units,[self.s]);self.assertEqual(sum(u['coverage_status']=='model_not_a_rule' for u in r['units']),4)
if __name__=='__main__':unittest.main()
