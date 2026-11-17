"""Provider selection; one schema and validator in app.py for all models."""
import getpass,json,time
from ollama_backend import Ollama,select_model

class Gemini:
    options={'temperature':0}
    def __init__(self,key):
        from google import genai
        self.client=genai.Client(api_key=key)
    def extract(self,model,prompt,section,schema):
        for attempt in range(3):
            try:
                response=self.client.models.generate_content(model=model,contents=prompt+'\n'+json.dumps(section),config={'response_mime_type':'application/json','response_json_schema':schema,'temperature':0})
                candidates=getattr(response,'candidates',None)
                if candidates:
                    reason=str(getattr(candidates[0],'finish_reason',''))
                    if 'MAX_TOKENS' in reason:raise RuntimeError('Incomplete Gemini output. Section not checkpointed.')
                if not response.text:raise RuntimeError('Gemini returned no JSON content.')
                return response.text
            except Exception as e:
                code=getattr(e,'code',None)
                if code in [429,500,502,503,504] and attempt<2:
                    print(f'Transient Gemini HTTP {code}; retrying...');time.sleep(2**attempt);continue
                # SDK exception messages can contain request data: do not echo them.
                raise RuntimeError(f'Gemini request failed ({type(e).__name__}, HTTP {code or "unknown"}). Check model access, key, quota and connectivity.') from None
    def close(self):self.client.close()

def choose_backend():
    print('\nEXTRACTION MODE\n [1] Offline - Ollama (local installed model)\n [2] Online  - Gemini (API key required)\n [3] Manual review - no model')
    while True:
        answer=input('Choose mode [3]: ').strip() or '3'
        if answer=='3':return None
        if answer=='1':
            client=Ollama();client.ensure_running();selected=select_model(client)
            if selected is None:return None
            print('Profile: 16K context, non-thinking, one unit at a time; model stays warm for 10 minutes. Use ollama ps during extraction to check GPU use.')
            return client,dict(selected,provider='ollama',options=dict(client.options),think=False,keep_alive='10m')
        if answer=='2':
            print('Selected sections will be sent to Google. API quota/billing applies.')
            model=input('Gemini model ID available to your account (Enter = back): ').strip()
            if not model:continue
            key=getpass.getpass('Gemini API key (hidden; not saved): ').strip()
            if not key:print('No key entered. Returning to mode selection.');continue
            client=Gemini(key);del key
            return client,{'name':model,'provider':'gemini','digest':None,'options':client.options}
        print('Choose 1, 2 or 3.')

def section_selection(text,sections):
    text=text.strip()
    if text.lower()=='all':return list(range(len(sections)))
    if text.lower().startswith('topic:'):
        query=text.split(':',1)[1].strip().casefold()
        if not query:raise ValueError('Enter a topic after topic:, e.g. topic:Medical Allowance')
        indices=[i for i,s in enumerate(sections) if not s.get('context_only') and query in (' / '.join(s.get('heading_path',[]))+' / '+(s.get('disclosure_title') or '')).casefold()]
        if not indices:raise ValueError('No sections match that topic.')
        return indices
    indices=list(dict.fromkeys(int(x.strip())-1 for x in text.split(',')))
    if any(i<0 or i>=len(sections) for i in indices):raise ValueError('Section number outside range.')
    return indices
