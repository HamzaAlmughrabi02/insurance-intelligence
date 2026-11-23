"""Real local HTTP tests for V2 isolation, stages, task CAS and source scope."""
import http.cookiejar,json,secrets,sys,threading,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'backend'))
import integration as app
import report_engine as eng
import v2_reports as v2
scratch=ROOT/'qa-isolated'/('v2-http-'+secrets.token_hex(4));app.base.DATA=scratch;app.base.DB=scratch/'app.sqlite3';app.base.UPLOADS=scratch/'uploads';app.init()
server=app.base.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
url='http://127.0.0.1:'+str(server.server_port);client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));csrf=''
def req(path,obj=None,headers=None):
 h={'X-CSRF-Token':csrf,**(headers or {})};raw=None
 if obj is not None:raw=json.dumps(obj).encode();h['Content-Type']='application/json'
 try:
  with client.open(urllib.request.Request(url+path,data=raw,headers=h),timeout=15) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
checks=[]
def check(name,value):assert value,name;checks.append(name);print('PASS',name)
try:
 check('workspace_requires_account',req('/api/workspace/cases')[0]==401)
 check('report_requires_account',req('/api/cases/missing/report')[0]==401)
 ticket=app.auth_sessions.issue_setup_invite();code,session=req('/api/auth/setup',{'username':'qa-v2-owner','password':secrets.token_urlsafe(24),'setup_ticket':ticket});assert code==201;csrf=session['csrf']
 # A UTF-8 filename must round-trip through the same binary upload route as the browser.
 _,upload=req('/api/cases',{'kind':'motor','client':'QA UPLOAD'})
 from urllib.parse import quote
 filename='وثيقة تأمين.pdf'
 request=urllib.request.Request(url+'/api/cases/'+upload['id']+'/documents',data=b'%PDF-1.4\nQA synthetic fixture',headers={'X-CSRF-Token':csrf,'X-Filename':quote(filename)},method='POST')
 with client.open(request,timeout=10) as response:check('arabic_filename_uploaded',response.status==201)
 _,uploaded=req('/api/cases/'+upload['id']);check('arabic_filename_preserved',uploaded['documents'][0]['original_name']==filename)
 _,c=req('/api/cases',{'kind':'motor','client':'QA SYNTHETIC'});case=c['id'];check('workspace_lists_draft',req('/api/workspace/cases')[1]['items'][0]['display_status']=='DRAFT');check('workspace_missing_case',req('/api/workspace/cases/missing/state')[0]==404);text='Invoice\nDoor JOD 100';d={'document_id':'qa-document','name':'invoice.pdf','page_count':1,'pages':[{'page':1,'text':text,'method':'native_pdf'}],'uncertainties':[]}
 result={'claim_version':1,'evidence':[d],'extracted':{}};report=eng.prepare(case,1,result);packet=eng.analyst_packet(report)
 with app.base.conn() as db:
  db.execute('INSERT INTO corrections VALUES(?,?,?)',(case,1,'{}'));db.execute("UPDATE cases SET status='review',result=? WHERE id=?",(json.dumps(result),case))
  db.execute('INSERT INTO report_runs(id,case_id,version,job_id,status,stage,report,packet,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',('qa-report',case,1,'WEB-QA','running','ANALYST',json.dumps(report),json.dumps(packet),app.base.now(),app.base.now()))
 check('review_waits_for_report',req('/api/cases/'+case+'/review',{'decision':'approve','note':'QA','version':1})[0]==409)
 check('stage_rejects_browser_or_wrong_secret',req('/api/integrations/v2/input',{'run_id':'qa-report','execution_id':'qa'})[0]==401)
 internal={'Authorization':'Bearer '+app.cfg['N8N_CALLBACK_TOKEN']}
 check('internal_origin_rejected',req('/api/integrations/v2/input',{'run_id':'qa-report'},headers={**internal,'Origin':url})[0]==401)
 code,data=req('/api/integrations/v2/input',{'run_id':'qa-report','execution_id':'qa'},internal);check('scope_input_loaded',code==200 and data['case_id']==case)
 check('second_execution_cannot_take_run',req('/api/integrations/v2/input',{'run_id':'qa-report','execution_id':'other'},internal)[0]==409)
 id=packet['sources'][0]['evidence_id'];raw={'observations':[{'text':'ورد مبلغ 100 في المستند.','kind':'DOCUMENT_STATEMENT','evidence_ids':[id]}]}
 code,audit=req('/api/integrations/v2/analyst',{'run_id':'qa-report','output':raw},internal);check('analyst_to_independent_audit',code==200 and len(audit['assertions'])==1)
 check('identical_analyst_callback_idempotent',req('/api/integrations/v2/analyst',{'run_id':'qa-report','output':raw},internal)[0]==200)
 check('conflicting_analyst_rejected',req('/api/integrations/v2/analyst',{'run_id':'qa-report','output':{}},internal)[0]==409)
 assertion=audit['assertions'][0];output={'reviews':[{'assertion_id':assertion['assertion_id'],'status':'INSUFFICIENT','reason':'لا يكفي للاعتماد','evidence_ids':[id]}]}
 code,published=req('/api/integrations/v2/publish',{'run_id':'qa-report','output':output},internal);check('checked_report_published',code==200)
 _,data=req('/api/cases/'+case+'/report');check('unsupported_assertion_withheld',not data['report']['model_assertions'] and len(data['report']['withheld'])==1)
 check('tasks_materialized',len(data['tasks'])==4)
 check('open_tasks_block_approval',req('/api/cases/'+case+'/review',{'decision':'approve','note':'QA','version':1})[0]==409)
 t=data['tasks'][0];change={'version':1,'task_id':t['id'],'revision':0,'state':'IN_PROGRESS','owner':'QA reviewer','due_date':'2026-12-01','note':'متابعة اصطناعية'}
 check('task_assignment_saved',req('/api/cases/'+case+'/followup',change)[0]==200)
 check('concurrent_task_overwrite_blocked',req('/api/cases/'+case+'/followup',change)[0]==409)
 _,other=req('/api/cases',{'kind':'motor','client':'QA OTHER'});check('cross_case_task_blocked',req('/api/cases/'+other['id']+'/followup',{**change,'version':0})[0]==409)
 check('foreign_document_role_rejected',req('/api/cases/'+case+'/document-role',{'version':1,'note':'QA','document_id':'foreign','role':'policy'})[0]==400)
 # Once tasks are closed, a new unanalysed supplement still blocks approval.
 with app.base.conn() as db:
  db.execute("UPDATE followup_tasks SET state='CLOSED' WHERE case_id=?",(case,))
  db.execute("INSERT INTO audit(case_id,action,actor,details,created_at) VALUES(?,?,?,?,?)",(case,'supplement_uploaded','QA','Synthetic new evidence','2099-01-01'))
 check('supplement_blocks_approval_after_tasks_closed',req('/api/cases/'+case+'/review',{'decision':'approve','note':'QA','version':1})[0]==409)
 # A stale browser must not reserve a new corrected version.
 with app.base.conn() as db:
  db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?)',('qa-upload',case,'fixture.pdf','sha',20,'qa-fixture'))
 check('stale_correction_version_rejected',req('/api/cases/'+case+'/reanalyze',{'version':0,'fields':{},'note':'QA'})[0]==409)
 check('note_only_update_accepted',req('/api/cases/'+case+'/reanalyze',{'version':1,'fields':{},'note':'QA new evidence'})[0]==202)
 check('old_version_stage_blocked',req('/api/integrations/v2/publish',{'run_id':'qa-report','output':output},internal)[0]==409)
 check('old_task_version_blocked',req('/api/cases/'+case+'/followup',{**change,'revision':1})[0]==409)
 code,old=req('/api/cases/'+case+'/report?version=1');check('old_report_read_only_with_correct_version',code==200 and old['version']==1 and old['is_current'] is False)
 with client.open(url+'/api/cases/'+case+'/report-print?version=1',timeout=10) as response:
  printed=response.read().decode('utf-8');check('print_keeps_requested_version_and_sources',response.status==200 and 'Door JOD 100' in printed and 'الإصدار 1' in printed)
 # A report must wait while the document preparation/OCR worker owns the memory budget.
 from unittest.mock import patch
 with app.base.conn() as db:
  db.execute("UPDATE report_runs SET version=2,status='queued' WHERE id='qa-report'")
  db.execute("UPDATE document_preparations SET status='running' WHERE case_id=?",(case,))
 with patch.object(v2.urllib.request,'urlopen') as send:
  v2.once();check('report_waits_for_ocr_preparation',not send.called)
 with app.base.conn() as db:check('waiting_report_stays_queued',db.execute("SELECT status FROM report_runs WHERE id='qa-report'").fetchone()[0]=='queued')
 print('V2 HTTP checks:',len(checks))
finally:server.shutdown();server.server_close()
