"""Generate local configuration without publishing secrets or replacing existing values."""
import json,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parent
config=ROOT/'local-config.json'
if not config.exists():
 config.write_text(json.dumps({key:secrets.token_urlsafe(32) for key in ['INSURANCE_API_TOKEN','N8N_DOCUMENT_TOKEN','N8N_CALLBACK_TOKEN','N8N_OUTBOUND_TOKEN']},indent=2),encoding='utf-8')
env=ROOT/'.env'
if not env.exists():env.write_text('POSTGRES_USER=insurance_admin\nPOSTGRES_DB=insurance_ai\nPOSTGRES_PASSWORD='+secrets.token_urlsafe(36)+'\n',encoding='utf-8')
print('Local configuration ready. Existing values were preserved. No passwords were printed.')
