"""Import isolated, inactive templates through the official n8n CLI. Never overwrite an existing setup."""
import json,os,secrets,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if (ROOT/'local-setup-state.json').exists():raise SystemExit('Already provisioned; use local-setup-state.json. Do not reimport over a running installation.')
if not (ROOT/'local-config.json').exists():raise SystemExit('Run python setup_local.py first.')
config=json.loads((ROOT/'local-config.json').read_text())
env={}
for line in (ROOT/'.env').read_text().splitlines():
 if '=' in line and not line.startswith('#'):
  key,value=line.split('=',1);env[key]=value
node=shutil.which('node');cli=Path(os.environ.get('APPDATA',''))/'npm/node_modules/n8n/bin/n8n'
if not node or not cli.exists():raise SystemExit('Install n8n using npm first. Windows npm installation is required.')
files={'workflow':'insurance-production.json','error':'insurance-error-handler.json','review_sync':'insurance-review-sync.json','assistant':'insurance-review-assistant.json'}
ids={key:secrets.token_hex(8) for key in [*files,'database','intake','callback','ollama']}
credentials=[
 {'id':ids['database'],'name':'Insurance PostgreSQL Local','type':'postgres','data':{'host':'127.0.0.1','port':5433,'database':env['POSTGRES_DB'],'user':env['POSTGRES_USER'],'password':env['POSTGRES_PASSWORD'],'ssl':'disable'}},
 {'id':ids['intake'],'name':'Insurance Local Web Intake','type':'httpHeaderAuth','data':{'name':'Authorization','value':'Bearer '+config['N8N_OUTBOUND_TOKEN']}},
 {'id':ids['callback'],'name':'Insurance Local Result Callback','type':'httpHeaderAuth','data':{'name':'Authorization','value':'Bearer '+config['N8N_CALLBACK_TOKEN']}},
 {'id':ids['ollama'],'name':'Insurance Local Ollama','type':'ollamaApi','data':{'baseUrl':'http://127.0.0.1:11434','apiKey':''}}
]
loaded={key:json.loads((ROOT/'n8n'/name).read_text(encoding='utf-8')) for key,name in files.items()}
mapping={w.get('meta',{}).get('templateWorkflowId'):ids[key] for key,w in loaded.items()}
workflows=[]
for key,workflow in loaded.items():
 workflow['id']=ids[key];workflow['active']=False
 old_error=workflow.get('settings',{}).get('errorWorkflow')
 if old_error:workflow['settings']['errorWorkflow']=mapping.get(old_error,ids['error'])
 for n in workflow['nodes']:
  kind=n['type'];parameters=n.get('parameters',{})
  if kind=='n8n-nodes-base.postgres':n['credentials']={'postgres':{'id':ids['database'],'name':'Insurance PostgreSQL Local'}}
  elif kind=='n8n-nodes-base.webhook' and parameters.get('authentication')=='headerAuth':n['credentials']={'httpHeaderAuth':{'id':ids['intake'],'name':'Insurance Local Web Intake'}}
  elif kind=='@n8n/n8n-nodes-langchain.lmChatOllama':n['credentials']={'ollamaApi':{'id':ids['ollama'],'name':'Insurance Local Ollama'}}
  elif parameters.get('authentication')=='genericCredentialType' and parameters.get('genericAuthType')=='httpHeaderAuth':n['credentials']={'httpHeaderAuth':{'id':ids['callback'],'name':'Insurance Local Result Callback'}}
 workflows.append(workflow)
(ROOT/'local-credentials.json').write_text(json.dumps(credentials),encoding='utf-8')
(ROOT/'local-workflow.json').write_text(json.dumps(workflows,ensure_ascii=False,indent=2),encoding='utf-8')
subprocess.run([node,str(cli),'import:credentials','--input='+str(ROOT/'local-credentials.json')],check=True)
subprocess.run([node,str(cli),'import:workflow','--input='+str(ROOT/'local-workflow.json')],check=True)
state={key:ids[key] for key in files};state['workflow_id']=ids['workflow'];state['url']='http://localhost:5678/workflow/'+ids['workflow']
(ROOT/'local-setup-state.json').write_text(json.dumps(state,indent=2))
print('Imported 4 inactive workflows; review them in n8n, then publish main, error handler, review synchronization and optional assistant.')
print('The presentation-only explainer is not imported because it shares webhook paths. The alternative external LLM path requires its own credential if enabled.')
