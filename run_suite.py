"""Run the development pilot. Python 3.10+, standard library only."""
import argparse
import csv
import json
from pathlib import Path
from engine import MODES, VERSION, discover, fingerprint
from reference import compare

BASE = Path(__file__).resolve().parent


def load_suite(path):
    suite = json.loads(Path(path).read_text(encoding='utf-8'))
    scenarios = suite['scenarios']
    if not scenarios or len({s['id'] for s in scenarios}) != len(scenarios):
        raise ValueError('Scenario IDs must be unique and the suite nonempty.')
    ids=[n['id'] for s in scenarios for n in s['nodes']]
    if len(ids)!=len(set(ids)):raise ValueError('KO IDs must be unique across the suite.')
    return suite


def run(suite, output_dir, max_hops=3):
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    rows=[]; results={}; checks={}
    packet=['# PRISM development review packet', '',
            'These are predictions from curated metadata. They are not volunteer labels or policy decisions.',
            'Yes = supported review candidate; Defer = unresolved interpretation requiring inspection; No = no supported path found within this model and hop limit.',
            'An affected scope describes the employees whose guidance needs review. Administrators are separate.', '']
    for s in suite['scenarios']:
        results[s['id']]={mode:discover(s,mode,max_hops) for mode in MODES}
        prism=results[s['id']]['prism']
        checks[s['id']]=compare(s,prism)
        if not checks[s['id']]['matches']:
            raise AssertionError(f"Independent reference mismatch: {s['id']}: {checks[s['id']]}")
        packet += [f"## {s['title']}", '', f"Change: {s['event']['after']['text']}", '',
                   f"Input hash: `{prism['input_sha256']}`. Maximum impact steps: {max_hops}.", '']
        for i in prism['items']:
            node=next(n for n in s['nodes'] if n['id']==i['ko_id'])
            packet += [f"### {i['ko_id']} — {i['title']}", '', node['text'], '',
                       f"**{i['status']}**. Classification: {i['directness']}. Additional unresolved evidence: {i['has_uncertainty']}.", '']
            for scope in i['affected_scopes']:
                packet += ['Affected scope: '+json.dumps(scope,ensure_ascii=False), '']
            for p in i['paths']:
                packet += [f"- {' → '.join(p['node_path'])}: {p['status']}; {p['field']}; {p['action']}; {p['reason']}"]
            for decision in prism['decisions']:
                if decision['node_path'][-1]==i['ko_id'] and decision['action']=='exclude':
                    packet += [f"- Excluded path {' → '.join(decision['node_path'])}: {decision['reason']}."]
            if not i['paths']:packet+=['No supported path survived within the configured boundary. This is not a legal determination of no impact.']
            packet+=['']
            rows.append({'item_id':i['ko_id'],'scenario_id':s['id'],
                         **{m:next(x['status'] for x in results[s['id']][m]['items'] if x['ko_id']==i['ko_id']) for m in MODES}})
    payload={'prototype_version':VERSION,'suite_sha256':fingerprint(suite),'max_hops':max_hops,
             'evaluation_status':'not_scored_without_independent_gold','reference_checks':checks,'results':results}
    (output_dir/'results.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (output_dir/'review_packet.md').write_text('\n'.join(packet),encoding='utf-8')
    with (output_dir/'predictions.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['item_id','scenario_id',*MODES]);w.writeheader();w.writerows(rows)
    with (output_dir/'prediction_matrix.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['item_id','PRISM','Local','Untyped'])
        for r in rows:w.writerow([r['item_id'],r['prism'],r['local'],r['untyped']])
    print(f"PRISM {VERSION}; {len(rows)} candidate pairs; {len(checks)} independent reference checks passed.")
    for m in MODES:
        print(m,', '.join(f"{label}={sum(r[m]==label for r in rows)}" for label in ['Yes','No','Defer']))
    print('No accuracy claim: independent gold labels have not been supplied.')
    print('Outputs:', output_dir)
    return payload,rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=BASE/'data/scenarios.json')
    p.add_argument('--out',type=Path,default=BASE/'output')
    p.add_argument('--max-hops',type=int,choices=[1,2,3],default=3)
    a=p.parse_args()
    try:run(load_suite(a.data),a.out,a.max_hops)
    except (ValueError,KeyError,OSError) as e:p.exit(2,f'Input error: {e}\n')


if __name__=='__main__':main()
