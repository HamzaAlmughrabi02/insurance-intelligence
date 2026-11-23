import os, json, sqlite3, uuid, hashlib, mimetypes, urllib.request
from pathlib import Path
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.environ.get('INSURANCE_DATA_DIR',str(ROOT/'data')))
DB=DATA/'app.sqlite3'
UPLOADS=DATA/'uploads'
MAX_SIZE=10*1024*1024
ALLOWED={'.pdf':b'%PDF-', '.png':b'\x89PNG\r\n\x1a\n', '.jpg':b'\xff\xd8\xff', '.jpeg':b'\xff\xd8\xff', '.xlsx':b'PK\x03\x04'}

def now():return datetime.now(timezone.utc).isoformat()
def conn():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
def init():
 DATA.mkdir(parents=True,exist_ok=True);UPLOADS.mkdir(parents=True,exist_ok=True)
 with conn() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,kind TEXT NOT NULL,client TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,created_at TEXT NOT NULL,result TEXT,review_note TEXT);
CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,case_id TEXT NOT NULL REFERENCES cases(id),original_name TEXT NOT NULL,sha256 TEXT NOT NULL,size INTEGER NOT NULL,path TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,case_id TEXT,action TEXT NOT NULL,actor TEXT NOT NULL,details TEXT NOT NULL,created_at TEXT NOT NULL);''')
def event(c,case_id,action,actor,details=''):
 c.execute('INSERT INTO audit(case_id,action,actor,details,created_at) VALUES(?,?,?,?,?)',(case_id,action,actor,details,now()))
def asdict(row):return dict(row) if row else None
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,status,obj):
  b=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def fail(self,status,msg):self.reply(status,{'error':msg})
 def auth(self,role=None):
  token=os.environ.get('INSURANCE_API_TOKEN','')
  if not token or self.headers.get('Authorization')!='Bearer '+token:self.fail(401,'Authentication required');return False
  if role and self.headers.get('X-Role')!=role:self.fail(403,'Required role: '+role);return False
  return True
 def body(self):
  n=int(self.headers.get('Content-Length','0'))
  if n>MAX_SIZE:self.fail(413,'Request too large');return None
  try:return json.loads(self.rfile.read(n))
  except (ValueError,UnicodeDecodeError):self.fail(400,'Invalid JSON');return None
 def do_GET(self):
  p=urlparse(self.path).path
  if p=='/':
   b=(ROOT/'index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  if p=='/api/health':return self.reply(200,{'status':'ok','n8n_configured':bool(os.environ.get('N8N_WEBHOOK_URL')),'document_access_configured':bool(os.environ.get('N8N_DOCUMENT_TOKEN'))})
  if p.startswith('/api/integrations/n8n/documents/'):
   secret=os.environ.get('N8N_DOCUMENT_TOKEN','')
   if not secret or self.headers.get('Authorization')!='Bearer '+secret:return self.fail(401,'Invalid document access token')
   doc_id=p.rsplit('/',1)[-1]
   with conn() as c:doc=c.execute('SELECT path,original_name FROM documents WHERE id=?',(doc_id,)).fetchone()
   if not doc:return self.fail(404,'Document not found')
   path=Path(doc['path'])
   if not path.is_file():return self.fail(404,'Document missing')
   content=path.read_bytes();self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(content)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(content);return
  if not self.auth():return
  with conn() as c:
   if p=='/api/cases':return self.reply(200,[asdict(r) for r in c.execute('SELECT id,kind,client,notes,status,created_at FROM cases ORDER BY created_at DESC')])
   if p=='/api/audit':return self.reply(200,[asdict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200')])
   if p.startswith('/api/cases/'):
    case_id=p.split('/')[3];r=c.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone()
    if not r:return self.fail(404,'Case not found')
    d=asdict(r);d['documents']=[asdict(x) for x in c.execute('SELECT id,original_name,sha256,size FROM documents WHERE case_id=?',(case_id,))];return self.reply(200,d)
  self.fail(404,'Not found')
 def do_POST(self):
  p=urlparse(self.path).path
  if p=='/api/integrations/n8n/result':
   secret=os.environ.get('N8N_CALLBACK_TOKEN','')
   if not secret or self.headers.get('Authorization')!='Bearer '+secret:return self.fail(401,'Invalid callback token')
   obj=self.body()
   if obj is None:return
   case_id=obj.get('case_id');result=obj.get('result')
   if not isinstance(result,dict) or not isinstance(case_id,str):return self.fail(400,'Expected case_id and result object')
   with conn() as c:
    r=c.execute('SELECT status FROM cases WHERE id=?',(case_id,)).fetchone()
    if not r:return self.fail(404,'Case not found')
    if r['status'] not in ('processing','queued'):return self.fail(409,'Case is not processing')
    c.execute('UPDATE cases SET result=?,status=? WHERE id=?',(json.dumps(result,ensure_ascii=False),'review',case_id));event(c,case_id,'result_received','n8n','Awaiting human review')
   return self.reply(200,{'status':'review'})
  if not self.auth():return
  if p=='/api/cases':
   obj=self.body()
   if obj is None:return
   kind=str(obj.get('kind','')).strip()[:100];client=str(obj.get('client','')).strip()[:100];notes=str(obj.get('notes','')).strip()[:1000]
   if not kind or not client:return self.fail(400,'kind and client required')
   case_id='INS-'+uuid.uuid4().hex[:10].upper()
   with conn() as c:c.execute('INSERT INTO cases(id,kind,client,notes,status,created_at) VALUES(?,?,?,?,?,?)',(case_id,kind,client,notes,'draft',now()));event(c,case_id,'created',getattr(self,'actor','operator'))
   return self.reply(201,{'id':case_id,'status':'draft'})
  if p.startswith('/api/cases/'):
   parts=p.split('/');case_id=parts[3];action=parts[4] if len(parts)>4 else ''
   with conn() as c:
    r=c.execute('SELECT status FROM cases WHERE id=?',(case_id,)).fetchone()
    if not r:return self.fail(404,'Case not found')
   if action=='documents':
    if r['status']!='draft':return self.fail(409,'Only drafts accept documents')
    name=unquote(self.headers.get('X-Filename','document')); name=Path(name).name[:120];ext=Path(name).suffix.lower()
    if ext not in ALLOWED:return self.fail(415,'Unsupported file extension')
    n=int(self.headers.get('Content-Length','0'))
    if not 0<n<=MAX_SIZE:return self.fail(413,'File must be 1 byte to 10 MB')
    content=self.rfile.read(n)
    if not content.startswith(ALLOWED[ext]):return self.fail(415,'File signature mismatch')
    doc_id=uuid.uuid4().hex;dest=UPLOADS/doc_id;dest.write_bytes(content);os.chmod(dest,0o600)
    with conn() as c:c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',(doc_id,case_id,name,hashlib.sha256(content).hexdigest(),n,str(dest)));event(c,case_id,'document_uploaded',getattr(self,'actor','operator'),doc_id)
    return self.reply(201,{'document_id':doc_id})
   if action=='submit':
    if r['status']!='draft':return self.fail(409,'Only drafts can be submitted')
    with conn() as c:
     docs=c.execute('SELECT id,original_name,sha256 FROM documents WHERE case_id=?',(case_id,)).fetchall()
     if not docs:return self.fail(400,'Upload a document first')
     c.execute('UPDATE cases SET status=? WHERE id=?',('queued',case_id));event(c,case_id,'queued','operator')
    url=os.environ.get('N8N_WEBHOOK_URL','')
    if not url:return self.reply(202,{'status':'queued','warning':'n8n webhook not configured'})
    # Only send metadata; document bytes remain local until a secure retrieval contract is agreed.
    payload=json.dumps({'case_id':case_id,'documents':[dict(x) for x in docs],'document_fetch_base':os.environ.get('INSURANCE_DOCUMENT_BASE_URL','http://127.0.0.1:'+os.environ.get('PORT','8765'))+'/api/integrations/n8n/documents/'}).encode()
    try:
     req=urllib.request.Request(url,data=payload,headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ.get('N8N_OUTBOUND_TOKEN','')})
     with urllib.request.urlopen(req,timeout=8) as response:
      if response.status>=300:raise ValueError('n8n rejected request')
     with conn() as c:c.execute('UPDATE cases SET status=? WHERE id=?',('processing',case_id));event(c,case_id,'dispatched','system')
     return self.reply(202,{'status':'processing'})
    except Exception:
     with conn() as c:event(c,case_id,'dispatch_failed','system','Check local n8n endpoint')
     return self.reply(202,{'status':'queued','warning':'n8n dispatch failed; retry integration after checking settings'})
   if action=='review':
    if not self.auth('supervisor'):return
    obj=self.body()
    if obj is None:return
    decision=obj.get('decision');note=str(obj.get('note','')).strip()[:2000]
    if r['status']!='review' or decision not in ('approve','reject') or not note:return self.fail(400,'Review requires pending case, decision and note')
    status='approved' if decision=='approve' else 'rejected'
    with conn() as c:c.execute('UPDATE cases SET status=?,review_note=? WHERE id=?',(status,note,case_id));event(c,case_id,status,getattr(self,'actor','supervisor'),note)
    return self.reply(200,{'status':status})
  self.fail(404,'Not found')
if __name__=='__main__':
 init();port=int(os.environ.get('PORT','8765'));print(f'Local app: http://127.0.0.1:{port}');ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
