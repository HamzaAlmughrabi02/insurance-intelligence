"""Prepare/import local credentials and the inactive workflow using the official CLI."""
import json,os,secrets,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if (ROOT/'local-setup-state.json').exists():raise SystemExit('Already provisioned. Use local-setup-state.json to find your imported workflow; do not reimport over a live workflow.')
if not (ROOT/'local-config.json').exists():raise SystemExit('Run python setup_local.py first.')
config=json.loads((ROOT/'local-config.json').read_text())
env={}
for line in (ROOT/'.env').read_text().splitlines():
 if '=' in line and not line.startswith('#'):
  key,value=line.split('=',1);env[key]=value
node=shutil.which('node')
cli=Path(os.environ.get('APPDATA',''))/'npm/node_modules/n8n/bin/n8n'
if not node or not cli.exists():raise SystemExit('Install n8n with npm first. This setup supports the Windows npm installation.')
ids={key:secrets.token_hex(8) for key in ['database','intake','callback','workflow']}
credentials=[
 {'id':ids['database'],'name':'Insurance PostgreSQL Local','type':'postgres','data':{'host':'127.0.0.1','port':5433,'database':env['POSTGRES_DB'],'user':env['POSTGRES_USER'],'password':env['POSTGRES_PASSWORD'],'ssl':'disable'}},
 {'id':ids['intake'],'name':'Insurance Local Web Intake','type':'httpHeaderAuth','data':{'name':'Authorization','value':'Bearer '+config['N8N_OUTBOUND_TOKEN']}},
 {'id':ids['callback'],'name':'Insurance Local Result Callback','type':'httpHeaderAuth','data':{'name':'Authorization','value':'Bearer '+config['N8N_CALLBACK_TOKEN']}}
]
workflow=json.loads((ROOT/'n8n/insurance-production.json').read_text(encoding='utf-8'));workflow['id']=ids['workflow'];workflow['active']=False
for n in workflow['nodes']:
 if n['type']=='n8n-nodes-base.postgres':n['credentials']={'postgres':{'id':ids['database'],'name':'Insurance PostgreSQL Local'}}
 if n['name']=='Web App Intake':n['credentials']={'httpHeaderAuth':{'id':ids['intake'],'name':'Insurance Local Web Intake'}}
 if n['name']=='Deliver Web Result':n['credentials']={'httpHeaderAuth':{'id':ids['callback'],'name':'Insurance Local Result Callback'}}
(ROOT/'local-credentials.json').write_text(json.dumps(credentials),encoding='utf-8')
(ROOT/'local-workflow.json').write_text(json.dumps(workflow,ensure_ascii=False,indent=2),encoding='utf-8')
subprocess.run([node,str(cli),'import:credentials','--input='+str(ROOT/'local-credentials.json')],check=True)
subprocess.run([node,str(cli),'import:workflow','--input='+str(ROOT/'local-workflow.json')],check=True)
(ROOT/'local-setup-state.json').write_text(json.dumps({'workflow_id':ids['workflow'],'url':'http://localhost:5678/workflow/'+ids['workflow']},indent=2))
print('Imported inactive workflow:',ids['workflow'])
print('Open n8n, review credentials and publish when ready. The alternative LLM path needs its own model credential if used.')
