"""Local-only Ollama HTTP adapter. No API key, proxies or cloud fallback."""
import json, os, shutil, subprocess, time
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise RuntimeError('Ollama redirected the request; refusing to leave the local endpoint.')

class Ollama:
    def __init__(self):
        self.options={'temperature':0,'num_ctx':16384,'num_predict':4096}
        self.base='http://127.0.0.1:11434'
        self.http=build_opener(ProxyHandler({}),NoRedirect())
    def request(self,path,payload=None,timeout=15):
        req=Request(self.base+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        try:
            with self.http.open(req,timeout=timeout) as response:return json.load(response)
        except HTTPError as e:
            raise RuntimeError(f'Ollama HTTP {e.code}: '+e.read(1500).decode(errors='replace')) from None
        except (URLError,TimeoutError) as e:
            raise RuntimeError('Cannot reach local Ollama, or generation timed out. Start Ollama (ollama serve), then retry. '+str(e)) from None
    def ensure_running(self,wait_seconds=20):
        """Start only a refused loopback service; never replace an existing server."""
        try:
            info=self.request('/api/tags',timeout=2)
            if not isinstance(info.get('models'),list):raise RuntimeError('Port 11434 did not return an Ollama model list.')
            return False
        except RuntimeError as error:
            if not any(x in str(error).lower() for x in ['connection refused','actively refused','10061']):raise
        exe=shutil.which('ollama')
        if not exe and os.name=='nt':
            candidate=Path(os.environ.get('LOCALAPPDATA',''))/'Programs'/'Ollama'/'ollama.exe'
            if candidate.is_file():exe=str(candidate)
        if not exe:raise RuntimeError('Ollama is not installed or not on PATH. Install Ollama, then reopen PRISM.')
        logdir=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'PRISM'/'logs'
        logdir.mkdir(parents=True,exist_ok=True);logpath=logdir/'ollama-server.log'
        env=os.environ.copy();env['OLLAMA_HOST']='127.0.0.1:11434'
        env['OLLAMA_NUM_PARALLEL']='1'
        kwargs={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
        print('Starting Ollama in the background...')
        with logpath.open('ab') as log:
            child=subprocess.Popen([exe,'serve'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=env,**kwargs)
        until=time.monotonic()+wait_seconds
        while time.monotonic()<until:
            try:
                if isinstance(self.request('/api/tags',timeout=1).get('models'),list):return True
            except RuntimeError:pass
            if child.poll() is not None:break
            time.sleep(.4)
        raise RuntimeError('Ollama did not become ready. See '+str(logpath)+'. Retry after checking the log; saved work is retained.')

    def models(self):
        return [m for m in self.request('/api/tags').get('models',[]) if not self.remote(m)]
    @staticmethod
    def remote(m):
        return bool(m.get('remote_host') or m.get('remote_model') or 'cloud' in m.get('name','').lower())
    def verify_local(self,model):
        info=self.request('/api/show',{'model':model})
        if self.remote(dict(info,name=model)):
            raise RuntimeError('Cloud-backed model refused. Select downloaded local model weights.')
        caps=info.get('capabilities',[])
        if caps and 'completion' not in caps:raise RuntimeError('Choose a text-generation model, not an embedding-only model.')
        return info
    def extract(self,model,prompt,section,schema):
        result=self.request('/api/chat',{'model':model,'messages':[{'role':'system','content':prompt+'\nJSON schema: '+json.dumps(schema)},{'role':'user','content':json.dumps(section)}],'format':schema,'stream':False,'think':False,'keep_alive':'10m','options':self.options},timeout=600)
        if not result.get('done') or result.get('done_reason')=='length':raise RuntimeError('Incomplete model output; this section was not checkpointed. Try a smaller section or another model.')
        text=result.get('message',{}).get('content')
        if not text:raise RuntimeError('Ollama returned no structured content.')
        count=result.get('eval_count',0);duration=result.get('eval_duration',0)
        if duration and count:print(f'Ollama output: {count} tokens, {count/(duration/1e9):.1f} tokens/s (generation only).')
        return text

def select_model(client):
    models=client.models()
    if not models:raise RuntimeError('No local models found. Download a text model with ollama pull MODEL_NAME, then retry.')
    print('\nINSTALLED LOCAL OLLAMA MODELS')
    for i,m in enumerate(models,1):print(f" [{i}] {m['name']} ({m.get('size',0)/1024**3:.1f} GiB)")
    while True:
        choice=input('Choose model number (Enter = manual review): ').strip()
        if not choice:return None
        if choice.isdigit() and 1<=int(choice)<=len(models):
            m=models[int(choice)-1];client.verify_local(m['name']);return m
        print('Choose one of the displayed numbers.')
