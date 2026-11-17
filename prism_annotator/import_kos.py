import scope_grounding
"""Preview-first import; never overwrite existing KOs or trust a filename."""
import hashlib,json,secrets,time

def records(payload):
    if isinstance(payload,list):return payload,{}
    if isinstance(payload,dict):
        for key in ['kos_verified','kos','kos_proposed']:
            if isinstance(payload.get(key),list):return payload[key],payload.get('manifest',{})
    raise ValueError('Expected a KO list or a snapshot with kos_verified/kos/kos_proposed.')

def preview(payload,sections,existing,validator):
    items,manifest=records(payload)
    if len(items)>10000:raise ValueError('Import at most 10,000 records at a time.')
    lookup={s['section_id']:s for s in sections};sha=sections[0]['source_sha256'] if sections else None;results=[];seen=set()
    for i,raw in enumerate(items):
        entry={'index':i,'original_id':str(raw.get('id',raw.get('ko_id',''))) if isinstance(raw,dict) else '', 'errors':[]}
        try:
            if not isinstance(raw,dict):raise ValueError('Record must be an object.')
            provenance=raw.get('provenance') or {};sem=raw.get('semantics') or {};evidence=raw.get('evidence') or {}
            expected=provenance.get('source_sha256') or raw.get('source_sha256') or manifest.get('source_sha256')
            if expected and expected!=sha:raise ValueError('Different source snapshot/file. Import this record in its matching Markdown project.')
            quote=raw.get('source_quote',evidence.get('source_quote',''))
            if not isinstance(quote,str) or not quote.strip():raise ValueError('Missing source quote.')
            matches=[s for s in sections if quote in s['raw_text']]
            sid=raw.get('section_id',provenance.get('section_id'))
            if sid in lookup and lookup[sid] in matches:matches=[lookup[sid]]
            if len(matches)>1:
                line=provenance.get('quote_line_start')
                if line:matches=[s for s in matches if s['line_start']<=line<=s['line_end']]
            if len(matches)!=1:raise ValueError('Quote absent or ambiguous in this project; exact source mapping is required.')
            s=matches[0];ident=entry['original_id'] or 'IMPORTED_'+hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()[:12]
            if ident in seen:raise ValueError('Duplicate ID within this import.')
            seen.add(ident)
            k={'id':ident,'section_id':s['section_id'],'summary':raw.get('summary',sem.get('summary','')),'source_quote':quote,'watched_fields':raw.get('watched_fields',sem.get('watched_fields',[])),'applicability_tuples':raw.get('applicability_tuples',[]),'scope_evidence':raw.get('scope_evidence',''),'additional_conditions':raw.get('additional_conditions',[]),'heading_path':s['heading_path'],'disclosure_title':s.get('disclosure_title'),'status':'proposed','note':raw.get('note',''),'validation_errors':[], 'import_metadata':{'original_id':entry['original_id'],'original_status':raw.get('status',raw.get('annotation_status','unknown')),'original_version':raw.get('version_id'),'source_hash_verified':bool(expected),'original_record':raw}}
            for field in ['rule_kind','context_evidence','scope_support','requirement_group_id','logical_operator','requirement_group_note']:
                if field in raw:k[field]=json.loads(json.dumps(raw[field]))
            for ref in k.get('context_evidence',[])+k.get('scope_support',[]):
                choices=[s for s in sections if ref.get('quote') and ref['quote'] in s['raw_text']]
                if ref.get('section_id') in lookup and lookup[ref['section_id']] in choices:continue
                if len(choices)!=1:raise ValueError('Context/scope citation cannot be mapped unambiguously.')
                ref['section_id']=choices[0]['section_id']
            k=scope_grounding.reconcile(k,lookup)
            errors=validator(k,lookup)
            if errors:raise ValueError('; '.join(errors))
            old=existing.get(ident)
            if old:
                fields=['section_id','summary','source_quote','watched_fields','applicability_tuples','additional_conditions']
                if all(old.get(f)==k.get(f) for f in fields):entry.update(action='skip',reason='Matching ID and content already present; existing decision preserved.');results.append(entry);continue
                raise ValueError('ID conflicts with an existing KO. No overwrite performed; resolve the ID in your import file.')
            if k['import_metadata']['original_status'] in ['rejected','deleted']:raise ValueError('Rejected/deleted records are not imported as active KOs.')
            entry.update(action='import',ko=k,can_preserve_approval=bool(expected and k['import_metadata']['original_status'] in ['verified','approved'] and not any(r['status']=='unsupported' for r in scope_grounding.report(k,lookup))))
        except (ValueError,TypeError,KeyError,AttributeError) as e:entry.update(action='blocked',errors=[str(e)])
        results.append(entry)
    return {'items':results,'counts':{x:sum(r['action']==x for r in results) for x in ['import','skip','blocked']},'notice':'Only records matching this project are imported. Other Markdown files need their own projects. Source verification is not a new semantic review.'}

def apply(db,plan,reviewer,preserve):
    now=time.time();ids=[]
    with db:
        for item in plan['items']:
            if item['action']!='import':continue
            k=item['ko'];k['import_metadata'].update(imported_by=reviewer,imported_at=now)
            if preserve and item['can_preserve_approval']:
                k['status']='approved';k['note']=(k.get('note','')+'\nImported prior approval; source hash and quote rechecked.').strip()
            db.execute('INSERT INTO state VALUES (?,?)',(k['id'],json.dumps(k)))
            db.execute('INSERT INTO audit VALUES (?,?,?,?,?)',(now,reviewer,k['id'],None,json.dumps(k)));ids.append(k['id'])
    return {'imported_ids':ids,'count':len(ids)}
