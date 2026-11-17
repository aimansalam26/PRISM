"""PRISM terminal launcher. Run `prism` after install.ps1 on Windows."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import webbrowser

HERE = Path(__file__).resolve().parent
CONFIG_DIR = Path(os.environ.get('PRISM_CONFIG_DIR') or Path.home() / '.prism')
CONFIG_FILE = CONFIG_DIR / 'settings.json'
BANNER = r'''
  ____   ____   ___  ____   __  __
 |  _ \ |  _ \ |_ _|/ ___| |  \/  |
 | |_) || |_) | | | \___ \ | |\/| |
 |  __/ |  _ <  | |  ___) || |  | |
 |_|    |_| \_\|___||____/ |_|  |_|

 HUMAN ANNOTATION WORKBENCH                         v0.13
 -------------------------------------------------------
 Source evidence -> Proposed KOs -> Human review
'''

def read_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    return {'handbook_root': '', 'projects_dir': str(HERE.parent / 'annotation_projects')}

def save_config(c):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    temp=CONFIG_FILE.with_suffix('.tmp')
    temp.write_text(json.dumps(c,indent=2),encoding='utf-8');temp.replace(CONFIG_FILE)

def path_input(prompt):
    return Path(input(prompt).strip().strip('"').strip("'")).expanduser().resolve()

def choose(items, title, label=str):
    if not items: print('\nNo matching items.');return None
    print('\n'+title)
    for i,x in enumerate(items,1):print(f'  [{i:2}] {label(x)}')
    while True:
        answer=input('\nChoose number (Enter = back): ').strip()
        if not answer:return None
        if answer.isdigit() and 1<=int(answer)<=len(items):return items[int(answer)-1]
        print('Please choose one of the displayed numbers.')

def configure(c):
    print('\nSETTINGS  /  Enter leaves a value unchanged')
    print('Handbook folder:',c['handbook_root'] or '(not configured)')
    raw=input('GitLab handbook folder: ').strip().strip('"')
    if raw:
        p=Path(raw).expanduser().resolve()
        if not p.is_dir():raise ValueError('That folder does not exist.')
        c['handbook_root']=str(p)
    print('Projects folder:',c['projects_dir'])
    raw=input('Save projects in: ').strip().strip('"')
    if raw:c['projects_dir']=str(Path(raw).expanduser().resolve())
    Path(c['projects_dir']).mkdir(parents=True,exist_ok=True);save_config(c)
    print('Settings saved. No API keys are stored.')

def select_source(c):
    mode=choose(['Search handbook files','Paste a Markdown file path'],'SELECT SOURCE')
    if mode is None:return None
    if mode.startswith('Paste'):
        p=path_input('Markdown file path: ')
        if not p.is_file() or p.suffix.lower()!='.md':raise ValueError('Select an existing .md file.')
        return p
    if not c['handbook_root']:
        p=path_input('GitLab handbook folder: ')
        if not p.is_dir():raise ValueError('Handbook folder does not exist.')
        c['handbook_root']=str(p);save_config(c)
    root=Path(c['handbook_root'])
    if not root.is_dir():raise ValueError('Configured handbook folder is missing. Update Settings.')
    content=root/'content'/'handbook'
    if not content.is_dir():content=root
    while True:
        query=input('\nFilename or path keywords (e.g. netherlands; Enter = back): ').strip().lower()
        if not query:return None
        words=query.split();matches=[]
        for p in content.rglob('*.md'):
            rel=p.relative_to(content).as_posix()
            if all(w in rel.lower() for w in words):matches.append(p)
        matches.sort()
        if len(matches)>40:
            print(f'{len(matches)} matches. Please use more specific keywords.');continue
        p=choose(matches,'MATCHING MARKDOWN FILES',lambda p:p.relative_to(content).as_posix())
        if p:return p

def project_list(c):
    root=Path(c['projects_dir'])
    if not root.exists():return []
    return sorted(p.parent for p in root.glob('*/manifest.json'))

def launch(source,project,verify=False):
    print('\nSTARTING WORKBENCH')
    print(' Source :',source)
    print(' Project:',project)
    print(' Follow the extraction prompts. Ctrl+C closes the server and returns here.\n')
    child=subprocess.Popen([sys.executable,str(HERE/'app.py'),'--source',str(source),'--project',str(project)]+(['--verify-only'] if verify else []))
    try:code=child.wait()
    except KeyboardInterrupt:
        try:code=child.wait(timeout=3)
        except subprocess.TimeoutExpired:child.terminate();code=child.wait()
    if code:print('\nWorkbench exited with an error. See the message above. Saved sections remain on disk.')

def new_project(c):
    source=select_source(c)
    if source is None:return
    default=re.sub(r'[^a-zA-Z0-9_-]+','-',source.stem).strip('-') or 'policy'
    name=input(f'\nProject name [{default}]: ').strip() or default
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',name):raise ValueError('Use 1-80 letters, numbers, hyphens or underscores; start with a letter/number.')
    if name.upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:raise ValueError('Choose a different project name.')
    project=Path(c['projects_dir'])/name
    if project.exists():raise ValueError('This project already exists. Use Open saved project or choose another name.')
    launch(source,project)

def reopen(c,verify=False):
    p=choose(project_list(c),'SAVED PROJECTS',lambda x:x.name)
    if p is None:return
    m=json.loads((p/'manifest.json').read_text(encoding='utf-8'));source=Path(m['source_file'])
    if not source.exists():
        print('Original source was moved. Select its unchanged replacement; SHA-256 will be checked.')
        source=path_input('Source .md path: ')
    if verify:launch(source,p,verify=True)
    else:launch(source,p)

def help_text():
    print('''
 HOW IT WORKS
  1. Select your GitLab Handbook Markdown file.
  2. Python slices it deterministically; no AI is used for parsing.
  3. Enter your reviewer name and choose offline Ollama, online Gemini or manual review.
  4. Choose a local model, or enter your Gemini model ID and hidden key.
  5. Choose pending/uncovered/full rerun; each bullet/paragraph gets a decision.
     Browser coverage checklist flags omissions and records human review.
  6. Import verified JSON via the browser Import KOs button if already available.
     Save decisions. SQLite retains annotations, trash and review history.
  7. Export from the browser. Ctrl+C in this terminal returns to the menu.

 IMPLEMENTED: Markdown parsing, Ollama/Gemini extraction, manual KOs,
 saved human review, per-unit coverage, requirement groups, rerun comparisons,
 shared graph connections, model-assisted edge proposals, audit/export, resume.
 SHARED GRAPH: open the graph link in the browser to connect KOs across files.

 Offline: local Ollama only. Online: Google Gemini with API key.
 Online mode sends selected sections to Google; API quota/billing applies.
 No automatic provider fallback. Unknown scope stays unknown.
 Exact quotes do not prove correct policy interpretation.

 Commands: prism | prism new | prism open | prism settings | prism help
           prism candidates | prism propose-edges | prism verify | prism traversal
''')

def propose_edges(c):
    from graph_store import GraphStore
    from extraction import choose_backend
    import edge_proposals
    graph=GraphStore(c['projects_dir']);client=None
    try:
        selection=choose_backend()
        if not selection:return
        client,selected=selection
        limit=int(input('Maximum candidate pairs to classify this run [12]: ').strip() or '12')
        edge_proposals.generate(graph,client,selected,limit)
        print('Open a project in manual review, then Candidate review. Suggestions are not saved edges.')
    finally:
        if client and hasattr(client,'close'):client.close()
        graph.db.close()

def candidate_export(c):
    from graph_store import GraphStore
    from candidates import report
    root=Path(c['projects_dir']).resolve()
    graph=GraphStore(root)
    try:
        result=report(graph)
        output=root/'edge_candidates.json'
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(str(len(result['candidates']))+' unordered candidate pairs saved to '+str(output))
        print('No edges created. Open a project in manual review, then Graph studio > Candidate review.')
    finally:graph.db.close()

def open_traversal():
    from traversal_workspace import ensure_running
    result=ensure_running()
    webbrowser.open(result['url'])
    print('Traversal workspace:',result['url'])
    print('The server stays open so review sessions remain available. Use the Annotation link to return to a running annotator.')

def build_scenario():
    script=HERE.parent/'build_handbook_scenario.py'
    if not script.is_file():raise ValueError('Install the matching traversal update in the PRISM root first.')
    subprocess.run([sys.executable,str(script)],cwd=HERE.parent,check=False)

def main():
    ap=argparse.ArgumentParser(description='PRISM human annotation workbench')
    ap.add_argument('action',nargs='?',choices=['new','open','settings','help','candidates','propose-edges','verify','traversal','build-scenario']);args=ap.parse_args()
    c=read_config()
    actions={'new':lambda:new_project(c),'open':lambda:reopen(c),'settings':lambda:configure(c),'help':help_text,'candidates':lambda:candidate_export(c),'propose-edges':lambda:propose_edges(c),'verify':lambda:reopen(c,verify=True),'traversal':open_traversal,'build-scenario':build_scenario}
    if args.action:
        actions[args.action]();return
    while True:
        print(BANNER)
        print('  [1] Start a new annotation project')
        print('  [2] Open / resume a saved project')
        print('  [3] Settings: handbook and project folders')
        print('  [4] Help and available features')
        print('  [5] Generate shared-graph candidate pairs')
        print('  [6] Propose edge types with Ollama / Gemini')
        print('  [7] Final verification (no extraction prompts)')
        print('  [8] Open traversal workspace')
        print('  [9] Build traversal scenario from verified annotations')
        print('  [0] Exit\n')
        answer=input('  prism > ').strip()
        if answer=='0':print('Goodbye. Saved annotations stay in your project folder.');return
        action={'1':'new','2':'open','3':'settings','4':'help','5':'candidates','6':'propose-edges','7':'verify','8':'traversal','9':'build-scenario'}.get(answer)
        if not action:print('Choose 0–9.');continue
        try:actions[action]()
        except (ValueError,OSError,json.JSONDecodeError) as e:print('\nCould not continue:',e)
        except KeyboardInterrupt:print('\nCancelled. Returning to menu.')
        input('\nPress Enter for the main menu...')
if __name__=='__main__':
    try:main()
    except (KeyboardInterrupt,EOFError):print('\nPRISM closed.')
    except (ValueError,OSError) as e:print('PRISM:',e);sys.exit(1)
