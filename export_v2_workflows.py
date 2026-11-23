"""Export sanitized live V2 templates; do not include credentials or execution data."""
import json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
state=json.loads((ROOT/'local-setup-state.json').read_text());db=sqlite3.connect((Path.home()/'.n8n/database.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
files={'workflow':'insurance-production.json','error':'insurance-error-handler.json','review_sync':'insurance-review-sync.json','assistant':'insurance-review-assistant.json','report':'insurance-v2-audited-report.json'}
for key,filename in files.items():
 row=dict(db.execute('SELECT * FROM workflow_entity WHERE id=?',(state[key],)).fetchone())
 out={k:json.loads(row[k]) if isinstance(row[k],str) else row[k] for k in ['nodes','connections','settings']}
 out.update(name=row['name'],active=False,pinData={},staticData=None,meta={'templateWorkflowId':state[key]})
 for n in out['nodes']:
  n.pop('credentials',None);n.pop('notes',None);n.pop('webhookId',None)
 (ROOT/'n8n'/filename).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('Exported five sanitized V2 workflow templates; no credentials or live data.')
