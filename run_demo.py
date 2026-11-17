"""Run the stipend chain first: a small example of accumulated scope."""
import argparse,json
from pathlib import Path
from run_suite import run,BASE

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=BASE/'output/demo')
    a=p.parse_args()
    scenario=json.loads((BASE/'data/policies.json').read_text(encoding='utf-8'))
    run({'schema_version':'0.3','snapshot_id':'stipend-demo','scenarios':[scenario]},a.out)
