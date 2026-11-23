"""Local integration extension. Original v0.4 server remains intact."""
import json, os, secrets, threading, time, re, urllib.request, urllib.error, logging
from pathlib import Path
from datetime import datetime
import server as base
import auth_sessions
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'local-config.json'
if not CONFIG.exists():
 CONFIG.write_text(json.dumps({k:secrets.token_urlsafe(32) for k in ('INSURANCE_API_TOKEN','N8N_DOCUMENT_TOKEN','N8N_CALLBACK_TOKEN','N8N_OUTBOUND_TOKEN')},indent=2))
cfg=json.loads(CONFIG.read_text())
os.environ.update(cfg)
os.environ.setdefault('N8N_WEBHOOK_URL','http://127.0.0.1:5678/webhook/insurance-web-intake')
PORT=int(os.environ.get('PORT','8766'))
base.DATA=Path(os.environ.get('INSURANCE_DATA_DIR',str(ROOT/'data')));base.DB=base.DATA/'app.sqlite3';base.UPLOADS=base.DATA/'uploads'

def init():
 base.init()
 auth_sessions.init()
 with base.conn() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS integration_jobs(job_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,attempts INTEGER DEFAULT 0,next_try REAL DEFAULT 0,error TEXT,UNIQUE(case_id,version));
CREATE TABLE IF NOT EXISTS evidence(document_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS callbacks(job_id TEXT PRIMARY KEY,digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS result_history(job_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,version INTEGER NOT NULL,result TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS corrections(case_id TEXT PRIMARY KEY,version INTEGER NOT NULL DEFAULT 1,fields TEXT NOT NULL DEFAULT '{}');''')

def extract(doc):
 path=Path(doc['path']).resolve()
 if path.parent!=base.UPLOADS.resolve():raise ValueError('File outside upload directory')
 out={'document_id':doc['id'],'name':doc['original_name'],'sha256':doc['sha256'],'pages':[],'method':'native_pdf','status':'ok','uncertainties':[]}
 try:
  ext=Path(doc['original_name']).suffix.lower()
  if ext=='.pdf':
   reader=PdfReader(path)
   if len(reader.pages)>100:raise ValueError('Page limit exceeded')
   for i,p in enumerate(reader.pages):out['pages'].append({'page':i+1,'text':(p.extract_text() or '')[:20000]})
  elif ext=='.xlsx':
   from openpyxl import load_workbook
   import zipfile
   with zipfile.ZipFile(path) as z:
    if sum(x.file_size for x in z.infolist())>50*1024*1024:raise ValueError('Expanded workbook too large')
   wb=load_workbook(path,read_only=True,data_only=True)
   for s in wb.worksheets[:10]:
    text='\n'.join(' | '.join(str(v or '') for v in row) for row in s.iter_rows(max_row=1000,max_col=30,values_only=True))
    out['pages'].append({'page':s.title,'text':text[:20000]})
    if len(text)>20000:out['uncertainties'].append('TEXT_TRUNCATED')
   wb.close();out['method']='openpyxl'
  else:
   from PIL import Image
   with Image.open(path) as image:image.verify()
   out.update(method='manual_image_review',status='requires_review');out['uncertainties'].append('IMAGE_OCR_NOT_AVAILABLE: review original image')
  if not any(p['text'].strip() for p in out['pages']):out['status']='requires_review';out['uncertainties'].append('NO_READABLE_TEXT')
 except Exception:
  out.update(status='requires_review',method='extraction_failed');out['uncertainties'].append('UNREADABLE_DOCUMENT')
 return out

def build(case_id,version,fields):
 with base.conn() as c:
  case=dict(c.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone())
  docs=[dict(r) for r in c.execute('SELECT * FROM documents WHERE case_id=?',(case_id,))]
 evidence=[extract(d) for d in docs]
 text='\n'.join(p['text'] for e in evidence for p in e['pages'])
 def match(pattern):
  m=re.search(pattern,text,re.I);return m.group(1).strip() if m else ''
 date=match(r'(?:Incident date|Date of incident)\s*\n(\d{1,2} \w{3} \d{4})')
 try:date=datetime.strptime(date,'%d %b %Y').date().isoformat()
 except ValueError:date=''
 claim={'claim_number':case_id,'policy_number':match(r'Policy number\s*\n([^\n]+)'), 'claim_type':'motor','accident_date':date,'vehicle_plate':match(r'(?:Vehicle registration|Registration)\s*\n([^\n]+)'), 'incident_description':match(r'Claimant statement:\s*([^\n]+)') or case['notes']}
 claim.update(fields);claim['claim_number']=case_id
 flags=[u for e in evidence for u in e['uncertainties']]
 policies=sorted(set(re.findall(r'\bPOL-[A-Z0-9-]+',text)))
 if len(policies)>1 or (policies and claim['policy_number'] not in policies):flags.append('CONFLICTING_POLICY_NUMBERS')
 if re.search(r'uncertain|discrepancy|not confirmed',text,re.I):flags.append('DOCUMENT_EVIDENCE_REQUIRES_REVIEW')
 if re.search(r'hood',text,re.I) and re.search(r'850',text):flags.append('HOOD_REPAIR_JOD_850_UNCERTAIN: compare invoice, incident report and inspection')
 with base.conn() as c:
  for e in evidence:c.execute('INSERT OR REPLACE INTO evidence VALUES(?,?,?)',(e['document_id'],case_id,json.dumps(e)))
 job=f'WEB-{case_id}-v{version}'
 field_sources={}
 for key,value in claim.items():
  if key in fields:field_sources[key]=[{'source':'supervisor_correction','version':version}]
  elif key=='claim_number':field_sources[key]=[{'source':'application_case_id'}]
  else:field_sources[key]=[{'document_id':e['document_id'],'page':p['page']} for e in evidence for p in e['pages'] if str(value) and str(value) in p['text']]
 return {'schema_version':'1.0','event_id':job,'event_type':'claim.submitted','job_id':job,'claim_id':case_id,'claim_version':version,'correlation_id':job,'occurred_at':base.now(),'claim_data':claim,'web_integration':True,'case_id':case_id,'evidence':evidence,'document_flags':flags,'field_sources':field_sources}

class Handler(auth_sessions.AuthMixin,base.Handler):
 def body(self):
  try:
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=base.MAX_SIZE:self.fail(413,'Invalid request size');return None
   obj=json.loads(self.rfile.read(n))
   if not isinstance(obj,dict):raise ValueError()
   return obj
  except (ValueError,UnicodeDecodeError):self.fail(400,'Expected JSON object');return None
 def do_GET(self):
  p=base.urlparse(self.path).path
  if self.auth_get(p):return
  if p=='/api/review-queue':
   if not self.auth():return
   with base.conn() as c:
    rows=c.execute("SELECT c.id,c.kind,c.client,c.status,c.created_at,c.result,(SELECT count(*) FROM documents d WHERE d.case_id=c.id) AS document_count FROM cases c WHERE c.status='review' ORDER BY c.created_at DESC").fetchall()
   items=[]
   for row in rows:
    item={key:row[key] for key in ['id','kind','client','status','created_at','document_count']}
    try:result=json.loads(row['result'] or '{}')
    except (ValueError,TypeError):result={}
    if not isinstance(result,dict):result={}
    fields=result.get('extracted') if isinstance(result.get('extracted'),dict) else {}
    flags=result.get('flags') if isinstance(result.get('flags'),list) else []
    findings=result.get('findings') if isinstance(result.get('findings'),list) else []
    item.update(policy_number=fields.get('policy_number'),claim_version=result.get('claim_version'),reasons=flags+findings,summary=result.get('summary',''))
    items.append(item)
   return self.reply(200,items)
  if p=='/api/health':return self.reply(200,{'status':'ok','app':'insurance-integration','account_login':True,'n8n_configured':bool(os.environ.get('N8N_WEBHOOK_URL')),'document_access_configured':bool(cfg.get('N8N_DOCUMENT_TOKEN'))})
  if p=='/api/system/status':
   if not self.auth():return
   import socket
   n8n=False;database=False
   try:
    with urllib.request.urlopen('http://127.0.0.1:5678/healthz',timeout=1) as response:n8n=response.status==200
   except Exception:pass
   try:
    with socket.create_connection(('127.0.0.1',5433),timeout=1):database=True
   except OSError:pass
   return self.reply(200,{'n8n_reachable':n8n,'database_port_reachable':database,'ready':n8n and database})
  if p.startswith('/api/cases/') and p.rsplit('/',1)[-1] in ('jobs','history'):
   if not self.auth():return
   table='integration_jobs' if p.endswith('/jobs') else 'result_history'
   columns='job_id,version,status,attempts,error' if table=='integration_jobs' else 'job_id,version,result,created_at'
   with base.conn() as c:return self.reply(200,[dict(r) for r in c.execute(f'SELECT {columns} FROM {table} WHERE case_id=? ORDER BY version',(p.split('/')[3],))])
  if p.startswith('/api/documents/') or p.startswith('/api/integrations/n8n/documents/'):
   integration=p.startswith('/api/integrations/')
   if integration:
    if self.headers.get('Authorization')!='Bearer '+cfg['N8N_DOCUMENT_TOKEN']:return self.fail(401,'Invalid document access token')
   elif not self.auth():return
   with base.conn() as c:r=c.execute('SELECT path,original_name FROM documents WHERE id=?',(p.rsplit('/',1)[-1],)).fetchone()
   if not r:return self.fail(404,'Document not found')
   path=Path(r['path']).resolve()
   if path.parent!=base.UPLOADS.resolve() or not path.is_file():return self.fail(404,'Document unavailable')
   from urllib.parse import quote,parse_qs
   mime=base.mimetypes.guess_type(r['original_name'])[0] or 'application/octet-stream'
   self._inline_document=parse_qs(base.urlparse(self.path).query).get('view')==['1'] and mime in ('application/pdf','image/png','image/jpeg')
   disposition='inline' if self._inline_document else 'attachment'
   content=path.read_bytes();self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Disposition',disposition+"; filename*=UTF-8''"+quote(r['original_name'],safe=''));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
  if p.startswith('/api/cases/') and p.endswith('/evidence'):
   if not self.auth():return
   with base.conn() as c:return self.reply(200,[json.loads(r[0]) for r in c.execute('SELECT payload FROM evidence WHERE case_id=?',(p.split('/')[3],))])
  return super().do_GET()
 def do_POST(self):
  p=base.urlparse(self.path).path
  if self.auth_post(p):return
  if p=='/api/integrations/n8n/result':
   if self.headers.get('Authorization')!='Bearer '+cfg['N8N_CALLBACK_TOKEN']:return self.fail(401,'Invalid callback token')
   o=self.body()
   if o is None:return
   result=o.get('result');job=o.get('job_id');case=o.get('case_id')
   if not isinstance(result,dict) or not isinstance(job,str):return self.fail(400,'Expected result and job_id')
   digest=base.hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
   with base.conn() as c:
    c.execute('BEGIN IMMEDIATE')
    r=c.execute('SELECT * FROM integration_jobs WHERE job_id=? AND case_id=?',(job,case)).fetchone()
    if not r:return self.fail(404,'Unknown job')
    old=c.execute('SELECT digest FROM callbacks WHERE job_id=?',(job,)).fetchone()
    if old:return self.reply(200,{'status':'duplicate'}) if old[0]==digest else self.fail(409,'Conflicting callback')
    latest=c.execute('SELECT MAX(version) FROM integration_jobs WHERE case_id=?',(case,)).fetchone()[0]
    if r['version']!=latest:return self.fail(409,'Stale analysis version')
    if result.get('final_claim_decision') is not None:return self.fail(400,'Final insurance decisions are prohibited')
    result['requires_human_review']=True
    c.execute('INSERT INTO callbacks VALUES(?,?)',(job,digest))
    c.execute('INSERT INTO result_history VALUES(?,?,?,?,?)',(job,case,r['version'],json.dumps(result,ensure_ascii=False),base.now()))
    c.execute("UPDATE cases SET status='review',result=? WHERE id=?",(json.dumps(result,ensure_ascii=False),case))
    c.execute("UPDATE integration_jobs SET status='completed',error=NULL WHERE job_id=?",(job,))
    base.event(c,case,'result_received','n8n',job)
   return self.reply(200,{'status':'review'})
  if p.startswith('/api/cases/') and p.rsplit('/',1)[-1] in ('submit','reanalyze','retry'):
   if not self.auth():return
   case=p.split('/')[3];action=p.rsplit('/',1)[-1]
   if action=='reanalyze' and not self.auth('supervisor'):return
   o=self.body()
   if o is None:return
   with base.conn() as c:
    c.execute('BEGIN IMMEDIATE')
    r=c.execute('SELECT status FROM cases WHERE id=?',(case,)).fetchone()
    if not r:return self.fail(404,'Case not found')
    if action=='retry':
     if r['status']!='failed':return self.fail(409,'Only failed cases may retry')
     c.execute("UPDATE integration_jobs SET status='queued',attempts=0,next_try=0 WHERE case_id=? AND version=(SELECT MAX(version) FROM integration_jobs WHERE case_id=?) AND status='failed'",(case,case))
     c.execute("UPDATE cases SET status='queued' WHERE id=? AND status IN ('failed','processing')",(case,));return self.reply(202,{'status':'queued'})
    if action=='submit' and r['status']!='draft':return self.fail(409,'Only drafts may submit')
    if action=='reanalyze' and r['status'] not in ('review','failed'):return self.fail(409,'Review or failed case required')
    if not c.execute('SELECT 1 FROM documents WHERE case_id=?',(case,)).fetchone():return self.fail(400,'Upload a document first')
    previous=c.execute('SELECT * FROM corrections WHERE case_id=?',(case,)).fetchone()
    version=previous['version']+1 if previous else 1
    fields=json.loads(previous['fields']) if previous else {}
    if action=='reanalyze':
     if not str(o.get('note','')).strip():return self.fail(400,'Correction reason required')
     changes=o.get('fields',{})
     allowed={'policy_number','accident_date','vehicle_plate','incident_description','claim_type'}
     if not isinstance(changes,dict) or any(k not in allowed or not isinstance(v,str) or len(v)>10000 for k,v in changes.items()):return self.fail(400,'Invalid correction fields')
     before=dict(fields);fields.update(changes)
     base.event(c,case,'corrected',self.actor,json.dumps({'before':before,'after':fields,'note':o['note'],'version':version}))
    # Serialize state reservation, preventing concurrent duplicate submissions.
    c.execute('INSERT OR REPLACE INTO corrections VALUES(?,?,?)',(case,version,json.dumps(fields)))
    c.execute("UPDATE cases SET status='preparing' WHERE id=?",(case,))
   try:payload=build(case,version,fields)
   except Exception:
    with base.conn() as c:c.execute("UPDATE cases SET status='failed' WHERE id=?",(case,))
    return self.fail(422,'Document preparation failed')
   with base.conn() as c:
    c.execute('INSERT INTO integration_jobs(job_id,case_id,version,payload,status) VALUES(?,?,?,?,?)',(payload['job_id'],case,version,json.dumps(payload),'queued'))
    c.execute("UPDATE cases SET status='queued' WHERE id=?",(case,));base.event(c,case,'queued',self.actor,payload['job_id'])
   return self.reply(202,{'status':'queued','job_id':payload['job_id']})
  return super().do_POST()

def worker():
 while True:
  try:
   with base.conn() as c:
    c.execute('BEGIN IMMEDIATE')
    expired=c.execute("SELECT job_id,case_id FROM integration_jobs WHERE status='dispatched' AND next_try<=? AND attempts>=5",(time.time(),)).fetchall()
    for job in expired:
     c.execute("UPDATE integration_jobs SET status='failed',error='CallbackTimeout' WHERE job_id=?",(job['job_id'],))
     c.execute("UPDATE cases SET status='failed' WHERE id=? AND status='processing'",(job['case_id'],))
     base.event(c,job['case_id'],'processing_failed','system','Callback timeout; retry required')
    r=c.execute("SELECT * FROM integration_jobs WHERE status IN ('queued','dispatched') AND next_try<=? AND attempts<5 ORDER BY version LIMIT 1",(time.time(),)).fetchone()
    if r:
     c.execute("UPDATE integration_jobs SET status='dispatching',attempts=attempts+1 WHERE job_id=?",(r['job_id'],))
     c.execute("UPDATE cases SET status='processing' WHERE id=? AND status IN ('queued','failed')",(r['case_id'],))
   if r:
    try:
     req=urllib.request.Request(os.environ['N8N_WEBHOOK_URL'],data=r['payload'].encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+cfg['N8N_OUTBOUND_TOKEN']})
     with urllib.request.urlopen(req,timeout=30) as response:response.read()
     with base.conn() as c:c.execute("UPDATE integration_jobs SET status='dispatched',next_try=? WHERE job_id=? AND status='dispatching'",(time.time()+90,r['job_id']))
    except Exception as e:
     with base.conn() as c:
      state='failed' if r['attempts']>=4 else 'queued'
      c.execute("UPDATE integration_jobs SET status=?,next_try=?,error=? WHERE job_id=? AND status='dispatching'",(state,time.time()+min(60,2**(r['attempts']+1)),type(e).__name__,r['job_id']))
      if state=='failed':c.execute("UPDATE cases SET status='failed' WHERE id=?",(r['case_id'],));base.event(c,r['case_id'],'processing_failed','system','Local n8n unavailable; retry required')
  except Exception:logging.exception('Integration worker error')
  time.sleep(1)

def recover():
 with base.conn() as c:
  preparing=c.execute("SELECT id FROM cases WHERE status='preparing'").fetchall()
  for case in preparing:
   c.execute("UPDATE cases SET status=CASE WHEN result IS NULL THEN 'draft' ELSE 'review' END WHERE id=?",(case['id'],))
   base.event(c,case['id'],'preparation_recovered','system','Interrupted preparation; existing evidence retained')
  exhausted=c.execute("SELECT job_id,case_id FROM integration_jobs WHERE status='dispatching' AND attempts>=5").fetchall()
  for job in exhausted:
   c.execute("UPDATE integration_jobs SET status='failed',error='InterruptedFinalAttempt' WHERE job_id=?",(job['job_id'],))
   c.execute("UPDATE cases SET status='failed' WHERE id=? AND status='processing'",(job['case_id'],))
  c.execute("UPDATE integration_jobs SET status='queued',next_try=0 WHERE status='dispatching' AND attempts<5")

if __name__=='__main__':
 init()
 recover()
 threading.Thread(target=worker,daemon=True).start()
 print(f'Insurance integration: http://127.0.0.1:{PORT}',flush=True)
 base.ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
