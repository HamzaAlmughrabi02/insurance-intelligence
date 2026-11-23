"""Versioned review outbox, execution errors and a case-scoped read-only assistant."""
import json,secrets,time,threading,urllib.request,urllib.error,re,hashlib
BASE=None
CFG=None
ASSISTANT_SLOTS=threading.BoundedSemaphore(1)

def init():
 with BASE.conn() as c:
  c.executescript('''
CREATE TABLE IF NOT EXISTS execution_links(execution_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,case_id TEXT NOT NULL,version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS runtime_errors(id INTEGER PRIMARY KEY AUTOINCREMENT,execution_id TEXT,case_id TEXT,node TEXT,message TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS review_events(event_id TEXT PRIMARY KEY,case_id TEXT,version INTEGER,payload TEXT,status TEXT,attempts INTEGER DEFAULT 0,next_try REAL DEFAULT 0,error TEXT);
CREATE TABLE IF NOT EXISTS assistant_requests(id TEXT PRIMARY KEY,case_id TEXT,version INTEGER,question TEXT,actor TEXT,expires REAL,calls INTEGER DEFAULT 0,status TEXT DEFAULT 'running');
CREATE TABLE IF NOT EXISTS assistant_reads(request_id TEXT,document_id TEXT,page TEXT,quote TEXT);
''')
  # Reconcile previously recorded local reviews without re-deciding any claim.
  rows=c.execute("SELECT * FROM cases WHERE status IN ('approved','rejected') AND review_note IS NOT NULL AND review_note!=''").fetchall()
  for row in rows:
   current=version(c,row['id'])
   try:recorded=json.loads(row['result'] or '{}').get('claim_version')
   except ValueError:continue
   if current<1 or recorded!=current:continue
   if c.execute('SELECT 1 FROM review_events WHERE case_id=? AND version=?',(row['id'],current)).fetchone():continue
   event='legacy-'+row['id']+'-v'+str(current)
   payload={'event_id':event,'case_id':row['id'],'claim_version':current,'decision':'approve' if row['status']=='approved' else 'reject','note':row['review_note'],'actor':'recorded_review_migration','occurred_at':BASE.now()}
   c.execute('INSERT OR IGNORE INTO review_events(event_id,case_id,version,payload,status) VALUES(?,?,?,?,?)',(event,row['id'],current,json.dumps(payload),'pending'))

def version(c,case):
 r=c.execute('SELECT version FROM corrections WHERE case_id=?',(case,)).fetchone()
 if r:return r[0]
 r=c.execute('SELECT MAX(version) FROM integration_jobs WHERE case_id=?',(case,)).fetchone()
 return r[0] or 0

def review_once():
 with BASE.conn() as c:
  c.execute('BEGIN IMMEDIATE')
  event=c.execute("SELECT * FROM review_events WHERE status='pending' AND next_try<=? ORDER BY rowid LIMIT 1",(time.time(),)).fetchone()
  if not event:return
  c.execute("UPDATE review_events SET status='sending',attempts=attempts+1 WHERE event_id=?",(event['event_id'],))
 try:
  req=urllib.request.Request('http://127.0.0.1:5678/webhook/insurance-review-sync',data=event['payload'].encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+CFG['N8N_OUTBOUND_TOKEN']})
  with urllib.request.urlopen(req,timeout=25) as r:ack=json.load(r)
  if ack.get('event_id')!=event['event_id'] or ack.get('status')!='synced':raise ValueError('Invalid review acknowledgment')
  with BASE.conn() as c:
   c.execute("UPDATE review_events SET status='synced',error=NULL WHERE event_id=?",(event['event_id'],))
   BASE.event(c,event['case_id'],'review_synced','system',event['event_id'])
 except Exception as e:
  with BASE.conn() as c:c.execute("UPDATE review_events SET status='pending',next_try=?,error=? WHERE event_id=?",(time.time()+min(300,2**min(event['attempts']+2,8)),type(e).__name__,event['event_id']))

def sync_worker():
 with BASE.conn() as c:c.execute("UPDATE review_events SET status='pending' WHERE status='sending'")
 while True:
  try:review_once()
  except Exception:pass
  time.sleep(2)

def tool(request_id,operation,args):
 with BASE.conn() as c:
  c.execute('BEGIN IMMEDIATE')
  request=c.execute("SELECT * FROM assistant_requests WHERE id=? AND status='running' AND expires>?",(request_id,time.time())).fetchone()
  if not request or request['calls']>=6:raise ValueError('Assistant request expired or tool budget exceeded')
  if request['version']!=version(c,request['case_id']):raise ValueError('Claim version changed')
  c.execute('UPDATE assistant_requests SET calls=calls+1 WHERE id=?',(request_id,))
  case=c.execute('SELECT result FROM cases WHERE id=?',(request['case_id'],)).fetchone()
  result=json.loads(case['result'] or '{}')
  evidence=result.get('evidence',[])
  if operation=='read_claim':
   returned_sources=[]
   for entries in result.get('field_sources',{}).values():
    for source in entries:
     if source.get('quote') and source.get('document_id'):returned_sources.append({k:source[k] for k in ('document_id','page','quote')})
   for finding in result.get('findings',[]):
    for source in finding.get('sources',[]):
     if source.get('quote') and source.get('document_id'):returned_sources.append({k:source[k] for k in ('document_id','page','quote')})
   for hit in returned_sources:c.execute('INSERT INTO assistant_reads VALUES(?,?,?,?)',(request_id,hit['document_id'],str(hit['page']),hit['quote']))
   return {'case_id':request['case_id'],'version':request['version'],'fields':result.get('extracted',{}),'field_quality':result.get('field_quality',{}),'findings':result.get('findings',[]),'flags':result.get('flags',[]),'sources':returned_sources,'documents':[{'document_id':e['document_id'],'name':e['name'],'pages':[p['page'] for p in e.get('pages',[])]} for e in evidence],'notice':'All extracted data is unverified; no coverage/payment decisions.'}
  if operation=='search_evidence':
   query=str(args.get('query',''))[:180];words=re.findall(r'[\w\u0600-\u06ff]+',query.lower())
   matches=[]
   for e in evidence:
    for p in e.get('pages',[]):
     text=str(p.get('text',''))
     for line in text.splitlines():
      score=sum(w in line.lower() for w in words if len(w)>1)
      if score:matches.append((score,{'document_id':e['document_id'],'page':p['page'],'quote':line[:1200]}))
   hits=[hit for _,hit in sorted(matches,key=lambda x:-x[0])[:8]]
  elif operation=='read_page':
   hits=[{'document_id':e['document_id'],'page':p['page'],'quote':p['text'][:16000]} for e in evidence for p in e.get('pages',[]) if e['document_id']==args.get('document_id') and str(p['page'])==str(args.get('page'))]
   if not hits:raise ValueError('Page outside this claim')
  else:raise ValueError('Unknown read-only tool')
  for hit in hits:c.execute('INSERT INTO assistant_reads VALUES(?,?,?,?)',(request_id,hit['document_id'],str(hit['page']),hit['quote']))
  return {'sources':hits,'notice':'Quoted OCR/text is evidence for review, not verified truth.'}

def finish(request_id,raw):
 try:
  if isinstance(raw,str):raw=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()))
 except (ValueError,TypeError):raw={}
 with BASE.conn() as c:
  r=c.execute('SELECT * FROM assistant_requests WHERE id=?',(request_id,)).fetchone()
  if not r or r['expires']<time.time() or r['version']!=version(c,r['case_id']):raise ValueError('Stale assistant response')
  sources=[dict(x) for x in c.execute('SELECT document_id,page,quote FROM assistant_reads WHERE request_id=?',(request_id,))]
  citations=[]
  refs=raw.get('citations',[]) if isinstance(raw,dict) else []
  for ref in (refs if isinstance(refs,list) else []):
   if not isinstance(ref,dict) or not isinstance(ref.get('quote'),str):continue
   quote=ref['quote'].strip()
   if len(quote)<8:continue
   if any(ref.get('document_id')==s['document_id'] and str(ref.get('page'))==s['page'] and quote in s['quote'] for s in sources):citations.append({'document_id':ref['document_id'],'page':ref['page'],'quote':quote})
  answer=raw.get('answer','') if isinstance(raw,dict) else ''
  forbidden=re.search(r'المطالبة\s+(?:مقبولة|مرفوضة)|التغطية\s+مؤكدة|approved claim|deny the claim|payment approved',str(answer),re.I)
  valid=isinstance(answer,str) and 0<len(answer)<=5000 and citations and not forbidden
  c.execute("UPDATE assistant_requests SET status=? WHERE id=?",('completed' if valid else 'insufficient_evidence',request_id))
  BASE.event(c,r['case_id'],'assistant_response',r['actor'],json.dumps({'request_id':request_id,'version':r['version'],'tool_calls':r['calls'],'citations':len(citations),'accepted':bool(valid)}))
 return {'status':'draft' if valid else 'insufficient_evidence','answer':answer if valid else 'لم أجد إجابة بمصادر كافية. راجع المستندات الأصلية أو حدّد سؤالك أكثر.','citations':citations if valid else [],'version':r['version'],'notice':'مسودة مساعد للمراجعة؛ الاقتباس لا يثبت صحة المستند أو استحقاق المطالبة.'}

class ReliabilityMixin:
 def internal(self):
  return not self.headers.get('Origin') and secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+CFG['N8N_CALLBACK_TOKEN'])
 def do_GET(self):
  path=BASE.urlparse(self.path).path
  if path.startswith('/api/cases/') and len(path.split('/'))==4:
   if not self.auth():return
   case=path.split('/')[3]
   with BASE.conn() as c:
    row=c.execute('SELECT * FROM cases WHERE id=?',(case,)).fetchone()
    if not row:return self.fail(404,'Case not found')
    data=dict(row);data['documents']=[dict(d) for d in c.execute('SELECT id,original_name,sha256,size FROM documents WHERE case_id=?',(case,))]
    data['current_version']=version(c,case)
    sync=c.execute('SELECT status FROM review_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case,)).fetchone()
    data['review_sync']=sync[0] if sync else None
    if data['status']=='failed':
     job=c.execute('SELECT payload FROM integration_jobs WHERE case_id=? ORDER BY version DESC LIMIT 1',(case,)).fetchone()
     data['failed_fields']=json.loads(job[0]).get('claim_data',{}) if job else {}
   return self.reply(200,data)
  return super().do_GET()
 def do_POST(self):
  path=BASE.urlparse(self.path).path
  if path in ('/api/integrations/n8n/started','/api/integrations/n8n/error','/api/integrations/n8n/assistant-tool','/api/integrations/n8n/assistant-finish','/api/integrations/n8n/assistant-sources'):
   if not self.internal():return self.fail(401,'Internal credential required')
   obj=self.body()
   if obj is None:return
   try:
    if path.endswith('/started'):
     intake=obj['intake'];job=intake['job_id'];case=intake['case_id']
     with BASE.conn() as c:
      r=c.execute('SELECT * FROM integration_jobs WHERE job_id=? AND case_id=?',(job,case)).fetchone()
      if not r or r['version']!=version(c,case) or json.loads(r['payload'])!=intake:return self.fail(409,'Stale or mismatched intake')
      c.execute('INSERT OR IGNORE INTO execution_links VALUES(?,?,?,?)',(str(obj['execution_id']),job,case,r['version']))
     return self.reply(200,intake)
    if path.endswith('/error'):
     with BASE.conn() as c:
      r=c.execute('SELECT * FROM execution_links WHERE execution_id=?',(str(obj.get('execution_id','')),)).fetchone()
      case=r['case_id'] if r else None
      c.execute('INSERT INTO runtime_errors(execution_id,case_id,node,message,created_at) VALUES(?,?,?,?,?)',(str(obj.get('execution_id','')),case,str(obj.get('node',''))[:150],str(obj.get('message','Workflow failed'))[:500],BASE.now()))
      if r and r['version']==version(c,case):
       c.execute("UPDATE integration_jobs SET status='failed',error=? WHERE job_id=? AND status!='completed'",('N8N_NODE_FAILURE: '+str(obj.get('node',''))[:120],r['job_id']))
       c.execute("UPDATE cases SET status='failed' WHERE id=? AND status IN ('queued','processing')",(case,))
     return self.reply(200,{'recorded':True})
    if path.endswith('/assistant-sources'):
     with BASE.conn() as c:
      r=c.execute("SELECT * FROM assistant_requests WHERE id=? AND status='running' AND expires>?",(obj['request_id'],time.time())).fetchone()
      if not r or r['version']!=version(c,r['case_id']):raise ValueError('Expired assistant request')
      sources=[dict(x) for x in c.execute('SELECT DISTINCT document_id,page,quote FROM assistant_reads WHERE request_id=? LIMIT 12',(obj['request_id'],))]
     for source in sources:source['quote']=source['quote'][:2000]
     return self.reply(200,{'request_id':obj['request_id'],'question':r['question'],'sources':sources[:8]})
    if path.endswith('/assistant-tool'):return self.reply(200,tool(obj['request_id'],obj['tool'],obj.get('args',{k:obj[k] for k in ('query','document_id','page') if k in obj})))
    return self.reply(200,finish(obj['request_id'],obj.get('output',{})))
   except (ValueError,KeyError,TypeError):return self.fail(422,'Invalid or stale integration request')
  if path.startswith('/api/cases/') and path.endswith('/review'):
   if not self.auth('supervisor'):return
   obj=self.body()
   if obj is None:return
   case=path.split('/')[3];decision=obj.get('decision');note=obj.get('note','')
   if decision not in ('approve','reject') or not isinstance(note,str) or not note.strip() or len(note)>2000:return self.fail(400,'Decision and written reason required')
   with BASE.conn() as c:
    c.execute('BEGIN IMMEDIATE');current=version(c,case)
    row=c.execute('SELECT status FROM cases WHERE id=?',(case,)).fetchone()
    if not row:return self.fail(404,'Case not found')
    if row['status']!='review' or obj.get('version')!=current:return self.fail(409,'Claim state/version changed; refresh before reviewing')
    state='approved' if decision=='approve' else 'rejected';event=secrets.token_hex(16)
    c.execute('UPDATE cases SET status=?,review_note=? WHERE id=?',(state,note.strip(),case))
    payload={'event_id':event,'case_id':case,'claim_version':current,'decision':decision,'note':note.strip(),'actor':self.actor,'occurred_at':BASE.now()}
    c.execute('INSERT INTO review_events(event_id,case_id,version,payload,status) VALUES(?,?,?,?,?)',(event,case,current,json.dumps(payload),'pending'))
    BASE.event(c,case,state,self.actor,json.dumps({'version':current,'reason':note.strip(),'event_id':event}))
   return self.reply(200,{'status':state,'review_sync':'pending','version':current})
  if path.startswith('/api/cases/') and path.endswith('/assistant'):
   if not self.auth():return
   obj=self.body()
   if obj is None:return
   question=obj.get('question','');case=path.split('/')[3]
   if not isinstance(question,str) or not 3<=len(question.strip())<=1000:return self.fail(400,'Question must be 3–1000 characters')
   if not ASSISTANT_SLOTS.acquire(blocking=False):return self.fail(429,'Assistant is busy; try shortly')
   try:
    with BASE.conn() as c:
     row=c.execute('SELECT result,status FROM cases WHERE id=?',(case,)).fetchone()
     if not row or not row['result']:return self.fail(409,'A completed analysis is required')
     if row['status'] not in ('review','approved','rejected'):return self.fail(409,'Analysis is in progress')
     request_id=secrets.token_urlsafe(24)
     c.execute('INSERT INTO assistant_requests(id,case_id,version,question,actor,expires) VALUES(?,?,?,?,?,?)',(request_id,case,version(c,case),question.strip(),self.actor,time.time()+150))
    payload={'request_id':request_id,'question':question.strip()}
    req=urllib.request.Request('http://127.0.0.1:5678/webhook/insurance-review-assistant',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+CFG['N8N_OUTBOUND_TOKEN']})
    with urllib.request.urlopen(req,timeout=140) as response:answer=json.load(response)
    if answer.get('status') not in ('draft','insufficient_evidence'):raise ValueError('Invalid assistant reply')
    return self.reply(200,answer)
   except Exception:
    if 'request_id' in locals():
     with BASE.conn() as c:
      c.execute("UPDATE assistant_requests SET status='failed' WHERE id=? AND status='running'",(request_id,))
      BASE.event(c,case,'assistant_failed',self.actor,request_id)
    return self.fail(503,'تعذر تشغيل المساعد الآن؛ يمكنك مراجعة الأدلة بالطريقة المعتادة.')
   finally:ASSISTANT_SLOTS.release()
  return super().do_POST()
