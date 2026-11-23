"""Isolate the V2 source configuration; no production data or secrets are copied."""
import json,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for name in ['backend/integration.py','backend/reliability.py','launcher.py','setup_n8n.py','backend/document_reader.py']:
 p=ROOT/name;s=p.read_text(encoding='utf-8')
 for old,new in [('insurance-readiness','insurance-v2-readiness'),('insurance-web-intake','insurance-v2-web-intake'),('insurance-review-sync','insurance-v2-review-sync'),('insurance-review-assistant','insurance-v2-review-assistant'),('8766','8786'),('8767','8787')]:
  if new not in s:s=s.replace(old,new)
 p.write_text(s,encoding='utf-8')
p=ROOT/'backend/auth_sessions.py';p.write_text(p.read_text(encoding='utf-8').replace("COOKIE='insurance_session'","COOKIE='insurance_v2_session'"),encoding='utf-8')
config=ROOT/'local-config.json'
if not config.exists():config.write_text(json.dumps({k:secrets.token_urlsafe(32) for k in ['INSURANCE_API_TOKEN','N8N_DOCUMENT_TOKEN','N8N_CALLBACK_TOKEN','N8N_OUTBOUND_TOKEN']},indent=2),encoding='utf-8')
env=ROOT/'.env'
if not env.exists():env.write_text('POSTGRES_USER=insurance_v2\nPOSTGRES_DB=insurance_ai_v2\nPOSTGRES_PASSWORD='+secrets.token_urlsafe(36)+'\nPOSTGRES_PORT=5434\nPOSTGRES_CONTAINER=insurance-v2-postgres\n',encoding='utf-8')
print('V2 private credentials, database identity and ports 8786/8787 isolated.')
