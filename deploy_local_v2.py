"""Provision only the isolated V2 database/workflows; never replace the original."""
import json,os,sqlite3,subprocess,sys,time
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parent
env=dict(l.split('=',1) for l in (ROOT/'.env').read_text().splitlines() if '=' in l and not l.startswith('#'))
assert env['POSTGRES_USER']=='insurance_v2' and env['POSTGRES_DB']=='insurance_ai_v2'
def sql(text,db='postgres'):
 r=subprocess.run(['docker','exec','-i','insurance-postgres','psql','-X','-v','ON_ERROR_STOP=1','-U','insurance_admin','-d',db],input=text.encode(),capture_output=True)
 if r.returncode:raise RuntimeError('V2 PostgreSQL provisioning failed. Check the local configuration and database permissions; SQL containing credentials is not echoed.')
 return r.stdout.decode()
password=env['POSTGRES_PASSWORD'];assert all(c.isalnum() or c in '-_' for c in password)
sql("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='insurance_v2') THEN CREATE ROLE insurance_v2 LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '"+password+"'; END IF; END $$;")
exists=sql("SELECT datname FROM pg_database WHERE datname='insurance_ai_v2';")
if 'insurance_ai_v2' not in exists:sql('CREATE DATABASE insurance_ai_v2 OWNER insurance_v2;')
count=subprocess.run(['docker','exec','insurance-postgres','psql','-X','-At','-U','insurance_admin','-d','insurance_ai_v2','-c',"SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"],capture_output=True,check=True).stdout.strip()
if count==b'0':
 schema=(ROOT/'database/schema.sql').read_text(encoding='utf-8')
 # Run as the isolated owner, not the production role.
 sql('SET ROLE insurance_v2;\n'+schema,'insurance_ai_v2')
subprocess.run([sys.executable,str(ROOT/'prepare_v2_n8n.py')],check=True)
state=json.loads((ROOT/'local-setup-state.json').read_text())
dbpath=Path.home()/'.n8n/database.sqlite'
with sqlite3.connect(dbpath) as db:
 assert not db.execute("SELECT id FROM execution_entity WHERE status IN ('running','new') LIMIT 1").fetchone(),'An execution is active; defer the n8n restart.'
 backup=ROOT/'backups';backup.mkdir(exist_ok=True)
 with sqlite3.connect(backup/('n8n-before-v2-'+str(int(time.time()))+'.sqlite3')) as dest:db.backup(dest)
original=ROOT.parent/'insurance-integration'
pid=int((original/'n8n.pid').read_text());proc=psutil.Process(pid)
assert any('n8n' in x.lower() for x in proc.cmdline())
proc.terminate();proc.wait(15)
cli=Path(os.environ['APPDATA'])/'npm/node_modules/n8n/bin/n8n'
try:
 imports=[('credentials','local-credentials.json'),('workflow','local-workflow.json')]
 only='report' if '--report-only' in sys.argv else 'workflow' if '--main-only' in sys.argv else None
 if only:
  prepared=json.loads((ROOT/'local-workflow.json').read_text(encoding='utf-8'))
  p=ROOT/'backups/report-only-import.json';p.write_text(json.dumps([w for w in prepared if w['id']==state[only]],ensure_ascii=False),encoding='utf-8')
  imports=[('workflow','backups/report-only-import.json')]
 for kind,file in imports:
  r=subprocess.run(['node',str(cli),'import:'+kind,'--input='+str(ROOT/file)],capture_output=True)
  if r.returncode:raise RuntimeError('V2 n8n import failed: '+r.stderr.decode(errors='replace')[-700:])
 for key in ([only] if only else ['error','review_sync','assistant','report','workflow']):
  r=subprocess.run(['node',str(cli),'publish:workflow','--id='+state[key]],capture_output=True)
  if r.returncode:raise RuntimeError('V2 workflow publication failed: '+r.stderr.decode(errors='replace')[-700:])
finally:
 sys.path.insert(0,str(original));import launcher
 launcher.start_n8n()
print('V2 database and five published workflows ready. Original workflows and database preserved.')
