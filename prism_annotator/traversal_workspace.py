"""Launch the existing root traversal UI on its own loopback port."""
import json,os,socket,subprocess,sys,time
from pathlib import Path
from urllib.request import build_opener,ProxyHandler
HERE=Path(__file__).resolve().parent

def ensure_running(annotation_port=8765,root=None,port=8766):
    root=Path(root or HERE.parent).resolve()
    if port==annotation_port:raise ValueError('Annotation and traversal ports must differ.')
    required=['app.py','engine.py','reference.py','ui_exports.py','ui/index.html','ui/styles.css','ui/app.js']
    missing=[str(root/name) for name in required if not (root/name).is_file()]
    if missing:raise ValueError('Traversal files missing: '+', '.join(missing)+'. Keep prism_annotator beside your existing traversal app.py and ui folder.')
    http=build_opener(ProxyHandler({}));url=f'http://127.0.0.1:{port}'
    def ready():
        try:
            with http.open(url+'/api/prism-workspace',timeout=1) as response:info=json.load(response)
            return info.get('workspace')=='prism-traversal' and info.get('root')==str(root) and info.get('annotation_port')==annotation_port
        except Exception:return False
    if ready():return {'url':url,'started':False}
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1',port))==0:raise ValueError(f'Port {port} is occupied by another service. Stop it or use your already-running traversal window.')
    logs=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'PRISM'/'logs';logs.mkdir(parents=True,exist_ok=True);logpath=logs/'traversal.log'
    kwargs={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
    with logpath.open('ab') as log:
        child=subprocess.Popen([sys.executable,str(HERE/'run_traversal.py'),'--root',str(root),'--port',str(port),'--annotation-port',str(annotation_port)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,cwd=root,**kwargs)
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        if ready():return {'url':url,'started':True}
        if child.poll() is not None:break
        time.sleep(.2)
    raise ValueError('Traversal did not start. See '+str(logpath))
