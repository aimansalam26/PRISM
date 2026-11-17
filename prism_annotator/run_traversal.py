"""Navigation wrapper; loads existing traversal code without replacing it."""
import argparse,importlib.util,json,sys
from pathlib import Path
from urllib.parse import urlsplit

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--port',type=int,default=8766);ap.add_argument('--annotation-port',type=int,default=8765);args=ap.parse_args()
    root=Path(args.root).resolve();assets=Path(__file__).resolve().parent
    sys.path.insert(0,str(root))
    spec=importlib.util.spec_from_file_location('prism_existing_traversal',root/'app.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original=module.Handler
    class Handler(original):
        def do_GET(self):
            if not self.local_request():return super().do_GET()
            path=urlsplit(self.path).path
            if path=='/api/prism-workspace':return self.send(200,{'workspace':'prism-traversal','root':str(root),'annotation_port':args.annotation_port})
            if path=='/favicon.svg':return self.send(200,(assets/'favicon.svg').read_bytes(),'image/svg+xml')
            if path=='/prism-navigation.css':return self.send(200,b'.prism-workspace-nav{display:flex;gap:24px;padding:12px 24px;background:#fff;border-bottom:1px solid #d6d9df;font:14px system-ui;color:#232a34}.prism-workspace-nav a{color:#315b85}', 'text/css')
            return super().do_GET()
        def send(self,status,data,mime='application/json; charset=utf-8',filename=None):
            if status==200 and mime.startswith('text/html'):
                text=data.decode('utf-8') if isinstance(data,bytes) else data
                head='<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/prism-navigation.css">'
                nav=f'<nav class="prism-workspace-nav" aria-label="Workspace"><strong>PRISM · Traversal</strong><a href="http://127.0.0.1:{args.annotation_port}/" target="prism-annotation">Annotation</a></nav>'
                text=text.replace('</head>',head+'</head>',1) if '</head>' in text else head+text
                import re
                text=re.sub(r'(<body\b[^>]*>)',lambda m:m[0]+nav,text,count=1,flags=re.I) if re.search(r'<body\b',text,re.I) else nav+text
                data=text
            return super().send(status,data,mime,filename)
    module.Handler=Handler;sys.argv=[str(root/'app.py'),'--port',str(args.port)];module.main()
if __name__=='__main__':main()
