'use strict';
let scopeRecord=null,scopeDirty=false;
const scopeDialog=document.createElement('dialog');scopeDialog.id='candidateScope';
scopeDialog.innerHTML='<div class="dialog-head"><h2>Edit applicability</h2><button type="button" id="scopeClose">Close</button></div><div class="dialog-body"><p id="scopeNodeTitle"></p><p id="scopeQuote" class="quote"></p><div id="candidateScopeFields"></div><details open><summary>Supporting context</summary><p class="muted">Select the heading or sentence that establishes this scope. A filename alone is not evidence.</p><div id="candidateContexts"></div></details><details><summary>Saved evidence checks</summary><div id="candidateScopeChecks"></div></details><p class="muted">Saving changes returns the KO to draft and makes existing connection reviews stale. Unknown dates remain unknown.</p><div class="dialog-footer"><button id="scopeSave" type="button">Save draft</button><button id="scopeApprove" type="button" class="primary">Save and approve KO</button></div><p id="candidateScopeError" class="error" role="alert"></p></div>';
document.body.append(scopeDialog);
const scopeEl=id=>document.getElementById(id);
function closeScope(){if(scopeDirty&&!confirm('Discard unsaved scope changes?'))return;scopeDialog.close();scopeDirty=false}
scopeEl('scopeClose').onclick=closeScope;scopeDialog.addEventListener('cancel',e=>{e.preventDefault();closeScope()});
async function editCandidateScope(key){
 try{const r=await fetch('/api/node/context?key='+encodeURIComponent(key));const v=await r.json();if(!r.ok)throw Error(v.error);scopeRecord=v;scopeDirty=false;
 scopeEl('scopeNodeTitle').textContent=v.ko.summary;scopeEl('scopeQuote').textContent=v.ko.source_quote;scopeEl('candidateScopeError').textContent='';
 const fields=scopeEl('candidateScopeFields');fields.replaceChildren();
 const labels={employment_types:'Employment types',org_roles:'Organisational roles',entities:'Employing entities',jurisdictions:'Jurisdictions',temporal_window:'Effective dates'};
 v.ko.applicability_tuples.forEach((t,i)=>{const group=elem('fieldset','');group.append(elem('legend','Applicability case '+(i+1)));
 for(const [dim,label] of Object.entries(labels)){
  for(let pos=0;pos<(dim==='temporal_window'?2:1);pos++){
   const row=elem('label',label+(dim==='temporal_window'?(pos===0?' — from':' — until'):''));const input=document.createElement('input');input.type='text';input.style.width='100%';input.dataset.dim=dim;input.dataset.tuple=i;input.dataset.position=pos;input.value=dim==='temporal_window'?t[dim][pos]:t[dim].join(' | ');input.setAttribute('aria-label',row.textContent+' case '+(i+1));
   input.oninput=()=>{scopeDirty=true;if(dim==='temporal_window')t[dim][pos]=input.value.trim()||'unknown';else t[dim]=input.value.split('|').map(x=>x.trim()).filter(Boolean);if(!t[dim].length)t[dim]=['unknown']};row.append(input);group.append(row)
  }
 }fields.append(group)});
 const contexts=scopeEl('candidateContexts');contexts.replaceChildren();const options=[...v.context_options];for(const c of v.ko.context_evidence||[])if(!options.some(x=>x.section_id===c.section_id&&x.quote===c.quote))options.push(c);
 for(const c of options){const label=elem('label','','context-choice');const input=document.createElement('input');input.type='checkbox';input.checked=(v.ko.context_evidence||[]).some(x=>x.section_id===c.section_id&&x.quote===c.quote);input.contextRef=c;input.onchange=()=>{scopeDirty=true};label.append(input,document.createTextNode(c.quote),elem('small',' · '+c.section_id));contexts.append(label)}
 scopeEl('candidateScopeChecks').replaceChildren();for(const r of v.scope_report)scopeEl('candidateScopeChecks').append(elem('p',r.dimension+': '+r.value+' — '+r.status+(r.reason?' · '+r.reason:'')));
 scopeDialog.showModal();
 }catch(e){$('error').textContent=e.message}
}
async function saveCandidateScope(decision){
 try{const contexts=[...scopeEl('candidateContexts').querySelectorAll('input:checked')].map(x=>({section_id:x.contextRef.section_id,quote:x.contextRef.quote,purpose:'scope'}));
 await post('/api/node/edit',{key:scopeRecord.key,fingerprint:scopeRecord.fingerprint,applicability_tuples:scopeRecord.ko.applicability_tuples,context_evidence:contexts,decision});scopeDirty=false;scopeDialog.close();await load();$('error').textContent='';$('notice').textContent=decision==='approved'?'KO approved. Related connections need review after a scope change.':'Scope saved. Review the KO and any affected connections.';
 }catch(e){scopeEl('candidateScopeError').textContent=e.message}
}
scopeEl('scopeSave').onclick=()=>saveCandidateScope('proposed');scopeEl('scopeApprove').onclick=()=>saveCandidateScope('approved');
window.addEventListener('beforeunload',e=>{if(scopeDirty){e.preventDefault();e.returnValue=''}});
