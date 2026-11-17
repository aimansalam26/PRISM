"""Synthetic end-to-end SQLite -> final verification -> scenario -> traversal check."""
import sys,copy,json,sqlite3,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'prism_annotator'))
from app import KO,check
from graph_store import GraphStore
import final_review
sys.path.insert(0,str(ROOT))
from build_handbook_scenario import build
from engine import discover
from reference import compare

def main():
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);p=root/'pilot';p.mkdir()
  quotes=['Full-time Netherlands staff receive EUR 150.','The deduction uses the allowance amount.']
  s={'section_id':'S','raw_text':'\n'.join(quotes),'line_start':1,'line_end':2,'heading_path':['Synthetic test'],'source_file':'fixture.md','source_sha256':'synthetic-hash'}
  (p/'manifest.json').write_text(json.dumps({'source_file':'fixture.md','source_sha256':'synthetic-hash'}));(p/'parsed_sections.json').write_text(json.dumps([s]))
  db=sqlite3.connect(p/'annotations.sqlite');db.execute('CREATE TABLE state(id TEXT PRIMARY KEY,body TEXT)')
  for i,q in enumerate(quotes):
   t={d:['unknown'] for d in ['employment_types','org_roles','entities','jurisdictions']};t['temporal_window']=['unknown','unknown']
   k=KO(section_id='S',summary=q,source_quote=q,watched_fields=['amount'] if i==0 else ['deduction'],applicability_tuples=[t],scope_evidence='',additional_conditions=[]).model_dump();k.update(id='KO_'+str(i),status='approved',validation_errors=[]);db.execute('INSERT INTO state VALUES (?,?)',(k['id'],json.dumps(k)))
  db.commit();g=GraphStore(root)
  try:
   g.save_edge({'source':'pilot::KO_0','target':'pilot::KO_1','relation_type':'CALCULATES_VALUE','field_mappings':[{'source_field':'amount','target_field':'deduction'}],'justification':'Synthetic fixture relationship','status':'approved','certainty':'confirmed'},'Synthetic curator')
   def accept(item):final_review.decide(g,{'id':item['id'],'fingerprint':item['fingerprint'],'decision':'accept','reason':'matches_source','evidence_checked':True},'Synthetic verifier',check)
   for item in final_review.packet(g,check)['items']:
    if item['kind']=='ko':accept(item)
   for item in final_review.packet(g,check)['items']:
    if item['kind']=='edge':accept(item)
   exported=dict(final_review.packet(g,check),graph=g.export())
   scenario=build(exported,{'id':'SYNTHETIC-BRIDGE-CHECK','root_ko':'pilot::KO_0','changed_fields':['amount'],'analysis_basis':'revised_clause_only','before':{'version_id':'old','text':'Full-time Netherlands staff receive EUR 100.','source':'synthetic-before.md'}})
   result=discover(scenario);assert result['items'][0]['status']=='Defer';assert compare(scenario,result)['matches'];assert result['items'][0]['paths'][0]['output_field']=='deduction'
   print('PASS: actual annotation SQLite + final verification + converter + mapped-field traversal; unknown scope remains Defer.')
  finally:g.db.close();db.close()
if __name__=='__main__':main()
