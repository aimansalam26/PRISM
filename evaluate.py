"""Read the research workbook without writing it; score independently frozen labels.

No optional packages are required. XLSX is read via its public XML format.
Formula caches are not used as gold. Blank/invalid labels are errors.
"""
import argparse,csv,json,zipfile,re
import xml.etree.ElementTree as ET
from pathlib import Path
from engine import fingerprint,MODES
from run_suite import BASE,load_suite

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_xlsx(path):
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        rels={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets={}
        for sh in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS):
            key=sh.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target=rels[key];target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            out={}
            for cell in ET.fromstring(z.read(target)).findall('.//s:sheetData/s:row/s:c',NS):
                if cell.find('s:f',NS) is not None:continue
                value=cell.find('s:v',NS)
                text=value.text if value is not None else ''
                if cell.attrib.get('t')=='s':text=strings[int(text)]
                elif cell.attrib.get('t')=='inlineStr':text=''.join(cell.find('s:is',NS).itertext())
                out[cell.attrib['r']]=text or ''
            sheets[sh.attrib['name']]=out
    return sheets


def read_gold(workbook,suite):
    sheets=read_xlsx(workbook);legend=sheets['Legend'];labels=sheets['Labels']
    if not legend.get('B20','').strip():raise ValueError('Record the gold freeze date in Legend B20 first.')
    if legend.get('B22')!=fingerprint(suite):raise ValueError('Workbook suite hash differs from the current scenarios. Do not mix versions.')
    expected={n['id'] for s in suite['scenarios'] for n in s['nodes'] if n['id']!=s['event']['root_ko']}
    gold={}
    for key,ident in labels.items():
        if not re.fullmatch(r'A\d+',key) or not ident.startswith('S'):continue
        row=key[1:]
        if ident not in expected:raise ValueError('Unknown scored item: '+ident)
        if ident in gold:raise ValueError('Duplicate gold item: '+ident)
        label=labels.get('K'+row,'');reason=labels.get('L'+row,'')
        if label not in {'Yes','No','Ambiguous'} or not reason.strip():raise ValueError('Missing/invalid gold label or source reason: '+ident)
        for col in ('F','H'):
            if labels.get(col+row) not in {'Yes','No','Ambiguous'}:raise ValueError('Both initial coder labels required: '+ident)
        for col in ('G','I'):
            if not labels.get(col+row,'').strip():raise ValueError('Both initial coder reasons required: '+ident)
        gold[ident]={'label':label,'reason':reason,'directness':labels.get('P'+row,'')}
    if set(gold)!=expected:raise ValueError('Workbook does not contain the complete candidate universe.')
    return gold


def score(gold,predictions):
    if set(gold)!=set(predictions):raise ValueError('Gold/prediction identifiers differ.')
    if any(p not in {'Yes','No','Defer'} for p in predictions.values()):raise ValueError('Every prediction must be Yes, No or Defer.')
    definite={k:v for k,v in gold.items() if v['label'] in {'Yes','No'}}
    tp=sum(gold[k]['label']=='Yes' and predictions[k]=='Yes' for k in definite)
    fp=sum(gold[k]['label']=='No' and predictions[k]=='Yes' for k in definite)
    fn=sum(gold[k]['label']=='Yes' and predictions[k]!='Yes' for k in definite)
    ratio=lambda a,b:a/b if b else None
    result={'scored_definite_gold':len(definite),'ambiguous_gold':len(gold)-len(definite),'tp':tp,'fp':fp,
            'fn_including_deferred_positives':fn,'precision':ratio(tp,tp+fp),'recall':ratio(tp,tp+fn),
            'f1':ratio(2*tp,2*tp+fp+fn),'review_volume':sum(v in {'Yes','Defer'} for v in predictions.values()),
            'deferred':sum(v=='Defer' for v in predictions.values()),
            'decision_coverage':ratio(sum(predictions[k]!='Defer' for k in definite),len(definite)),
            'review_capture_recall':ratio(sum(gold[k]['label']=='Yes' and predictions[k] in {'Yes','Defer'} for k in definite),tp+fn)}
    for group in ('direct','indirect'):
        members=[k for k in definite if gold[k]['label']=='Yes' and gold[k].get('directness')==group]
        complete=all(v['label']!='Yes' or v.get('directness') in {'direct','indirect'} for v in gold.values())
        result[group+'_recall']=ratio(sum(predictions[k]=='Yes' for k in members),len(members)) if complete else None
        result[group+'_gold_count']=len(members)
    result['positive_gold_missing_directness']=sum(v['label']=='Yes' and v.get('directness') not in {'direct','indirect'} for v in gold.values())
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workbook',type=Path,default=BASE/'3_Label_Matrix.xlsx')
    p.add_argument('--data',type=Path,default=BASE/'data/scenarios.json')
    p.add_argument('--results',type=Path,default=BASE/'output/results.json')
    p.add_argument('--out',type=Path,default=BASE/'output/evaluation.json')
    a=p.parse_args()
    try:
        suite=load_suite(a.data);gold=read_gold(a.workbook,suite)
        run=json.loads(a.results.read_text(encoding='utf-8'))
        if run['suite_sha256']!=fingerprint(suite):raise ValueError('Results were produced from different data.')
        metrics={}
        for mode in MODES:
            pred={i['ko_id']:i['status'] for s in run['results'].values() for i in s[mode]['items']}
            metrics[mode]=score(gold,pred)
            events=[]
            for s in run['results'].values():
                part={i['ko_id']:i['status'] for i in s[mode]['items']}
                events.append(score({k:gold[k] for k in part},part))
            metrics[mode]['macro']={key:(sum(vals)/len(vals) if vals else None) for key in ['precision','recall','f1'] for vals in [[e[key] for e in events if e[key] is not None]]}
            metrics[mode]['macro_event_denominators']={key:sum(e[key] is not None for e in events) for key in ['precision','recall','f1']}
        for m in MODES:
            n=metrics['untyped']['review_volume']
            metrics[m]['review_volume_reduction_vs_untyped']=1-metrics[m]['review_volume']/n if n else None
        report={'suite_sha256':fingerprint(suite),'gold_sha256':fingerprint(gold),'max_hops':run['max_hops'],
                'interpretation':'Descriptive development pilot; not held-out evidence or a non-inferiority test.',
                'scope_and_propagation':'Record independent scope/path judgements in the workbook. These are not inferred from KO-level scores.', 'metrics':metrics}
        a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print('Wrote',a.out)
    except (ValueError,KeyError,OSError,zipfile.BadZipFile) as e:p.exit(2,f'Evaluation not run: {e}\n')


if __name__=='__main__':main()
