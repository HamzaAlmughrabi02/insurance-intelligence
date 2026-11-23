"""Durable report generation, scoped n8n stages, follow-up tasks and role assignment."""
import hashlib,html,json,re,secrets,time,threading,urllib.request,uuid
from pathlib import Path
import report_engine as engine
BASE=None;CFG=None
def configure(base,cfg):
 global BASE,CFG
 BASE,CFG=base,cfg
def init():
 with BASE.conn() as c:
  c.executescript('''
CREATE TABLE IF NOT EXISTS report_runs(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,version INTEGER NOT NULL,job_id TEXT NOT NULL UNIQUE,status TEXT NOT NULL,stage TEXT NOT NULL,attempts INTEGER DEFAULT 0,report TEXT NOT NULL,packet TEXT NOT NULL,assertions TEXT,analyst_digest TEXT,verifier_digest TEXT,error TEXT,execution_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS document_roles(document_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,role TEXT NOT NULL,actor TEXT NOT NULL,note TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report_snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL,case_id TEXT NOT NULL,version INTEGER NOT NULL,attempt INTEGER NOT NULL,report TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL,UNIQUE(run_id,attempt));
CREATE TABLE IF NOT EXISTS followup_tasks(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,version INTEGER NOT NULL,task_key TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'OPEN',owner TEXT NOT NULL DEFAULT '',due_date TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 0,note TEXT NOT NULL DEFAULT '',UNIQUE(case_id,version,task_key));
''')
def current(c,case):
 r=c.execute('SELECT version FROM corrections WHERE case_id=?',(case,)).fetchone()
 return r[0] if r else 0
def validrun(c,id):
 r=c.execute('SELECT * FROM report_runs WHERE id=?',(id,)).fetchone()
 if not r or r['version']!=current(c,r['case_id']):raise ValueError('STALE_REPORT_SCOPE')
 return r
def save(c,id,report,status,stage,error=None):
 c.execute('UPDATE report_runs SET report=?,status=?,stage=?,error=?,updated_at=? WHERE id=?',(json.dumps(report,ensure_ascii=False),status,stage,error,BASE.now(),id))
def publish(c,r,report,error=None):
 # Pure schema and source scope checks are repeated at the publication boundary.
 for a in report['model_assertions']:
  assert a['evidence_ids'] and all(e in report['sources'] and report['sources'][e]['readable'] for e in a['evidence_ids'])
 report['schema_version']=engine.VERSION;report['publication_policy']='EXTRACTIVE_ONLY_FOR_MODEL_TEXT';report['generated_at']=BASE.now();report['run_id']=r['id'];report['execution_id']=r['execution_id'];report['model_status']='UNAVAILABLE_OR_INVALID' if error else 'REVIEW_COMPLETED';report['model_name']='qwen3-vl:2b-instruct';report['quality_state']='PARTIAL' if error or not report['coverage']['complete'] or report['withheld'] else 'READY_FOR_HUMAN_REVIEW'
 save(c,r['id'],report,'completed','PUBLISHED',error)
 c.execute('INSERT OR IGNORE INTO report_snapshots(run_id,case_id,version,attempt,report,error,created_at) VALUES(?,?,?,?,?,?,?)',(r['id'],r['case_id'],r['version'],r['attempts'],json.dumps(report,ensure_ascii=False),error,BASE.now()))
 c.execute("UPDATE followup_tasks SET state='SUPERSEDED',revision=revision+1 WHERE case_id=? AND version<? AND state NOT IN ('CLOSED','WAIVED','SUPERSEDED')",(r['case_id'],r['version']))
 for task in report['tasks']:
  c.execute('INSERT OR IGNORE INTO followup_tasks(id,case_id,version,task_key,payload) VALUES(?,?,?,?,?)',(engine.uid(r['case_id'],r['version'],task['key']),r['case_id'],r['version'],task['key'],json.dumps(task,ensure_ascii=False)))
 BASE.event(c,r['case_id'],'v2_report_published','report_gate',json.dumps({'version':r['version'],'run_id':r['id'],'model_assertions':len(report['model_assertions']),'withheld':len(report['withheld']),'quality':report['quality_state']}))
def enqueue():
 with BASE.conn() as c:
  rows=c.execute("SELECT h.* FROM result_history h LEFT JOIN report_runs r ON r.job_id=h.job_id WHERE r.id IS NULL").fetchall()
  for row in rows:
   if row['version']!=current(c,row['case_id']):continue
   roles={r['document_id']:r['role'] for r in c.execute('SELECT * FROM document_roles WHERE case_id=?',(row['case_id'],))}
   report=engine.prepare(row['case_id'],row['version'],json.loads(row['result']),roles);packet=engine.analyst_packet(report);now=BASE.now()
   c.execute('INSERT OR IGNORE INTO report_runs(id,case_id,version,job_id,status,stage,report,packet,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),row['case_id'],row['version'],row['job_id'],'queued','WAITING',json.dumps(report,ensure_ascii=False),json.dumps(packet,ensure_ascii=False),now,now))
def once():
 enqueue()
 with BASE.conn() as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute("SELECT 1 FROM document_preparations WHERE status='running' LIMIT 1").fetchone():return
  r=c.execute("SELECT * FROM report_runs WHERE status='queued' ORDER BY rowid LIMIT 1").fetchone()
  if not r:return
  if r['version']!=current(c,r['case_id']):c.execute("UPDATE report_runs SET status='superseded' WHERE id=?",(r['id'],));return
  c.execute("UPDATE report_runs SET status='running',stage='ANALYST',attempts=attempts+1,updated_at=? WHERE id=?",(BASE.now(),r['id']))
 try:
  req=urllib.request.Request('http://127.0.0.1:5678/webhook/insurance-v2-report',data=json.dumps({'run_id':r['id']}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+CFG['N8N_OUTBOUND_TOKEN']})
  with urllib.request.urlopen(req,timeout=300) as res:res.read()
  with BASE.conn() as c:
   done=c.execute('SELECT status FROM report_runs WHERE id=?',(r['id'],)).fetchone()
   if done[0]!='completed':raise ValueError('No checked report receipt')
 except Exception as e:
  with BASE.conn() as c:
   c.execute('BEGIN IMMEDIATE');latest=c.execute('SELECT * FROM report_runs WHERE id=?',(r['id'],)).fetchone()
   if latest['status']=='completed':return
   if latest['version']!=current(c,latest['case_id']):c.execute("UPDATE report_runs SET status='superseded' WHERE id=?",(r['id'],));return
   report=json.loads(latest['report']);report['model_assertions']=[]
   report['withheld'].append({'text':'لم تكتمل مراجعة النموذج.','reason':type(e).__name__})
   publish(c,latest,report,'MODEL_PIPELINE_UNAVAILABLE')
def worker():
 with BASE.conn() as c:c.execute("UPDATE report_runs SET status='queued',stage='RECOVERED' WHERE status='running'")
 while True:
  try:once()
  except Exception:
   import logging;logging.exception('V2 report worker')
  time.sleep(2)

class ReportMixin:
 def do_GET(self):
  p=BASE.urlparse(self.path).path;parts=p.split('/')
  if len(parts)==5 and parts[:3]==['','api','cases'] and parts[4] in ('report','report-print'):
   if not self.auth():return
   case=parts[3]
   with BASE.conn() as c:
    if not c.execute('SELECT 1 FROM cases WHERE id=?',(case,)).fetchone():return self.fail(404,'Case not found')
    from urllib.parse import parse_qs
    latest=current(c,case);requested=parse_qs(BASE.urlparse(self.path).query).get('version',[str(latest)])[0]
    try:v=int(requested)
    except ValueError:return self.fail(400,'Invalid report version')
    if v<1 or v>latest:return self.fail(400,'Invalid report version')
    r=c.execute('SELECT * FROM report_runs WHERE case_id=? AND version=?',(case,v)).fetchone()
    tasks=[{**json.loads(t['payload']),**{k:t[k] for k in ('id','version','state','owner','due_date','revision','note')}} for t in c.execute('SELECT * FROM followup_tasks WHERE case_id=? AND version=?',(case,v))]
    history=[dict(h) for h in c.execute("SELECT version,updated_at,stage FROM report_runs WHERE case_id=? AND status='completed' ORDER BY version DESC",(case,))]
    stale=c.execute('SELECT MAX(updated_at) FROM document_roles WHERE case_id=?',(case,)).fetchone()[0]
    additions=c.execute('SELECT MAX(created_at) FROM audit WHERE case_id=? AND action=?',(case,'supplement_uploaded')).fetchone()[0]
    previous=c.execute("SELECT version,report FROM report_runs WHERE case_id=? AND version<? AND status='completed' ORDER BY version DESC LIMIT 1",(case,v)).fetchone()
   report=json.loads(r['report']) if r and r['status']=='completed' else None;changes=None
   if report and previous:
    old=json.loads(previous['report']);oldfs={x['id']:x for x in old['findings']};newfs={x['id']:x for x in report['findings']}
    changes={'previous_version':previous['version'],'fields':[{'field':k,'before':old['fields'].get(k),'after':report['fields'].get(k)} for k in old['fields'].keys()|report['fields'].keys() if old['fields'].get(k)!=report['fields'].get(k)],'findings_added':[f['text'] for key,f in newfs.items() if key not in oldfs],'findings_removed':[f['text'] for key,f in oldfs.items() if key not in newfs],'previous_read_pages':old['coverage']['read_pages'],'read_pages':report['coverage']['read_pages']}
   obj={'case_id':case,'version':v,'is_current':v==latest,'status':r['status'] if r else 'waiting_for_analysis','stage':r['stage'] if r else 'INTAKE','error':r['error'] if r else None,'role_changes_pending':bool(r and v==latest and max(stale or '',additions or '')>r['created_at']),'tasks':tasks,'history':history,'changes':changes,'report':report}
   if parts[4]=='report-print':
    if not obj['report']:return self.fail(409,'Report not ready')
    return self.print_report(obj)
   return self.reply(200,obj)
  return super().do_GET()
 def print_report(self,obj):
  r=obj['report'];esc=lambda x:html.escape(str(x));sources=r['sources']
  rows=''.join('<tr><td>'+esc(f['text'])+'</td><td>'+''.join('<p>'+esc(sources[e]['document_name'])+' / '+esc(sources[e]['page'])+': '+esc(sources[e]['quote'])+'</p>' for e in f.get('evidence_ids',[]) if e in sources)+'</td></tr>' for f in r['findings']+r['model_assertions'])
  cov=''.join('<li>'+esc(d['name'])+': '+esc(d['observed_pages'])+' / '+esc(d['expected_pages'] if d['expected_pages'] is not None else 'غير معروف')+'؛ '+('قراءة كاملة' if d['complete'] else 'قراءة غير مكتملة')+'</li>' for d in r['coverage']['documents'])
  tasks=''.join('<li>'+esc(t['title'])+' — '+esc(t['state'])+' — '+esc(t['owner'])+' — '+esc(t['reason'])+'</li>' for t in obj['tasks'])
  data=('<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>تقرير '+esc(obj['case_id'])+'</title><style>body{font:16px/1.8 Tahoma;margin:40px;color:#233c3b}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:12px;text-align:right}tr{break-inside:avoid}blockquote{white-space:pre-wrap}button{padding:12px}@media print{button{display:none}}</style><button onclick="window.print()">طباعة / حفظ PDF</button><h1>تقرير مراجعة المركبة</h1><p>'+esc(obj['case_id'])+' · الإصدار '+str(obj['version'])+' · '+esc(r['generated_at'])+'</p><p>'+esc(r['decision_notice'])+'</p><h2>تغطية القراءة</h2><ul>'+cov+'</ul><h2>الملاحظات ومصادرها</h2><table><tr><th>الملاحظة</th><th>الدليل</th></tr>'+rows+'</table><h2>مهام الاستكمال</h2><ul>'+tasks+'</ul><p>معلومات محجوبة عن التقرير: '+str(len(r['withheld']))+'؛ حالة مراجعة النموذج: '+esc(r['model_status'])+'</p></html>').encode()
  self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def do_POST(self):
  p=BASE.urlparse(self.path).path;parts=p.split('/')
  if p.startswith('/api/integrations/v2/'):
   if self.headers.get('Origin') or not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+CFG['N8N_CALLBACK_TOKEN']):return self.fail(401,'Internal access required')
   obj=self.body()
   if obj is None:return
   try:
    with BASE.conn() as c:
     c.execute('BEGIN IMMEDIATE');r=validrun(c,obj.get('run_id'));report=json.loads(r['report'])
     action=parts[-1]
     if action=='input':
      if r['status']!='running':return self.fail(409,'Report not running')
      execution=str(obj.get('execution_id',''))
      if r['execution_id'] and r['execution_id']!=execution:return self.fail(409,'Report execution already bound')
      c.execute('UPDATE report_runs SET execution_id=? WHERE id=?',(execution,r['id']))
      return self.reply(200,json.loads(r['packet']))
     raw=obj.get('output',{});digest=engine.uid(raw)
     if action=='analyst':
      if r['analyst_digest']:
       if r['analyst_digest']!=digest:return self.fail(409,'Conflicting analyst callback')
       return self.reply(200,engine.verifier_packet(report,json.loads(r['assertions'])))
      if r['status']!='running' or r['stage']!='ANALYST':return self.fail(409,'Invalid report stage')
      report['analyst_valid']=isinstance(engine.parse(raw).get('observations'),list)
      assertions,rejected=engine.proposals(report,raw,{s['evidence_id'] for s in json.loads(r['packet'])['sources']});report['withheld']+=rejected
      if not report['analyst_valid']:report['withheld'].append({'text':'تعذرت قراءة مخرجات المحلّل.','reason':'INVALID_ANALYST_OUTPUT'})
      c.execute('UPDATE report_runs SET assertions=?,analyst_digest=? WHERE id=?',(json.dumps(assertions,ensure_ascii=False),digest,r['id']))
      save(c,r['id'],report,'running','VERIFIER')
      return self.reply(200,engine.verifier_packet(report,assertions))
     if action=='publish':
      if r['verifier_digest']:
       if r['verifier_digest']!=digest:return self.fail(409,'Conflicting verifier callback')
       return self.reply(200,{'status':'published','run_id':r['id']})
      if r['status']!='running' or r['stage']!='VERIFIER':return self.fail(409,'Invalid report stage')
      assertions=json.loads(r['assertions'] or '[]');engine.gate(report,assertions,raw)
      c.execute('UPDATE report_runs SET verifier_digest=? WHERE id=?',(digest,r['id']))
      malformed=not isinstance(engine.parse(raw).get('reviews'),list)
      publish(c,r,report,'INVALID_VERIFIER_OUTPUT' if malformed else 'INVALID_ANALYST_OUTPUT' if report.get('analyst_valid') is False else None)
      return self.reply(200,{'status':'published','run_id':r['id']})
     return self.fail(404,'Unknown report stage')
   except (ValueError,TypeError,KeyError):return self.fail(409,'Invalid or stale report scope')
  if len(parts)==5 and parts[:3]==['','api','cases'] and parts[4] in ('followup','document-role','supplements','report-retry','review'):
   action=parts[4];case=parts[3]
   if action=='review':
    if not self.auth('supervisor'):return
    obj=self.body()
    if obj is None:return
    self._v2_cached_body=obj
    with BASE.conn() as c:
     v=current(c,case);r=c.execute("SELECT status,created_at FROM report_runs WHERE case_id=? AND version=?",(case,v)).fetchone()
     pending=c.execute("SELECT 1 FROM followup_tasks WHERE case_id=? AND version=? AND state IN ('OPEN','IN_PROGRESS') LIMIT 1",(case,v)).fetchone()
     roles=c.execute('SELECT MAX(updated_at) FROM document_roles WHERE case_id=?',(case,)).fetchone()[0]
     additions=c.execute("SELECT MAX(created_at) FROM audit WHERE case_id=? AND action='supplement_uploaded'",(case,)).fetchone()[0]
    if not r or r['status']!='completed':return self.fail(409,'Wait for the checked V2 report before recording review')
    if obj.get('decision')=='approve' and (pending or max(roles or '',additions or '')>r['created_at']):return self.fail(409,'Complete or explicitly waive follow-up tasks and reanalyze role changes before approval')
    return super().do_POST()
   if not self.auth('supervisor'):return
   if action=='supplements':return self.supplement(case)
   obj=self.body()
   if obj is None:return
   with BASE.conn() as c:
    c.execute('BEGIN IMMEDIATE');v=current(c,case);row=c.execute('SELECT status FROM cases WHERE id=?',(case,)).fetchone()
    if not row:return self.fail(404,'Case not found')
    if type(obj.get('version')) is not int or obj['version']!=v:return self.fail(409,'Stale case version')
    if row['status'] not in ('review','failed'):return self.fail(409,'Case is not editable for follow-up')
    note=obj.get('note','')
    if not isinstance(note,str) or not note.strip() or len(note)>2000:return self.fail(400,'Written reason required')
    if action=='document-role':
     if obj.get('role') not in {*engine.ROLES,'unknown'} or not c.execute('SELECT 1 FROM documents WHERE id=? AND case_id=?',(obj.get('document_id'),case)).fetchone():return self.fail(400,'Invalid document role')
     c.execute('INSERT OR REPLACE INTO document_roles VALUES(?,?,?,?,?,?)',(obj['document_id'],case,obj['role'],self.actor,note,BASE.now()))
     BASE.event(c,case,'document_role_changed',self.actor,json.dumps(obj,ensure_ascii=False));return self.reply(200,{'status':'reanalysis_required'})
    if action=='report-retry':
     r=c.execute('SELECT * FROM report_runs WHERE case_id=? AND version=?',(case,v)).fetchone()
     if not r or r['status']!='completed' or not r['error']:return self.fail(409,'Only a failed model report may retry')
     report=json.loads(r['report']);report['model_assertions']=[];report['withheld']=[]
     c.execute("UPDATE report_runs SET status='queued',stage='WAITING',report=?,assertions=NULL,analyst_digest=NULL,verifier_digest=NULL,execution_id=NULL,error=NULL WHERE id=?",(json.dumps(report,ensure_ascii=False),r['id']))
     BASE.event(c,case,'report_retry',self.actor,note);return self.reply(202,{'status':'queued'})
    task=c.execute('SELECT * FROM followup_tasks WHERE id=? AND case_id=? AND version=?',(obj.get('task_id'),case,v)).fetchone()
    if not task:return self.fail(404,'Task not found')
    if type(obj.get('revision')) is not int or task['revision']!=obj['revision']:return self.fail(409,'Task changed; reload')
    if obj.get('state') not in ('OPEN','IN_PROGRESS','CLOSED','WAIVED'):return self.fail(400,'Invalid task state')
    owner=obj.get('owner','');due=obj.get('due_date','')
    if not isinstance(owner,str) or len(owner)>100 or not isinstance(due,str):return self.fail(400,'Invalid task fields')
    if due:
     from datetime import date
     try:date.fromisoformat(due)
     except ValueError:return self.fail(400,'Invalid due date')
    c.execute('UPDATE followup_tasks SET state=?,owner=?,due_date=?,note=?,revision=revision+1 WHERE id=?',(obj['state'],owner,due,note,obj['task_id']))
    BASE.event(c,case,'followup_changed',self.actor,json.dumps({'before':dict(task),'after':obj},ensure_ascii=False));return self.reply(200,{'status':'saved'})
  return super().do_POST()
 def supplement(self,case):
  # Stream raw upload only after auth; record snapshot version in the request header.
  from urllib.parse import unquote
  with BASE.conn() as c:
   c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT status FROM cases WHERE id=?',(case,)).fetchone()
   if not row or row['status'] not in ('review','failed'):return self.fail(409,'Only review/failed cases accept supplements')
   if self.headers.get('X-Claim-Version')!=str(current(c,case)):return self.fail(409,'Stale upload version')
   name=Path(unquote(self.headers.get('X-Filename','document'))).name[:120];ext=Path(name).suffix.lower();n=int(self.headers.get('Content-Length','0'))
   if ext not in BASE.ALLOWED or not 0<n<=BASE.MAX_SIZE:return self.fail(400,'Invalid file')
   data=self.rfile.read(n)
   if len(data)!=n or not data.startswith(BASE.ALLOWED[ext]):return self.fail(400,'Invalid file signature')
   digest=hashlib.sha256(data).hexdigest()
   if c.execute('SELECT 1 FROM documents WHERE case_id=? AND sha256=?',(case,digest)).fetchone():return self.fail(409,'Document already uploaded')
   id=uuid.uuid4().hex;path=BASE.UPLOADS/id;path.write_bytes(data)
   c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',(id,case,name,digest,n,str(path)))
   BASE.event(c,case,'supplement_uploaded',self.actor,name)
  return self.reply(201,{'document_id':id,'status':'reanalysis_required'})
