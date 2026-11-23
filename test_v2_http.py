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
 check('report_requires_account',req('/api/cases/missing/report')[0]==401)
 ticket=app.auth_sessions.issue_setup_invite();code,session=req('/api/auth/setup',{'username':'qa-v2-owner','password':secrets.token_urlsafe(24),'setup_ticket':ticket});assert code==201;csrf=session['csrf']
 _,c=req('/api/cases',{'kind':'motor','client':'QA SYNTHETIC'});case=c['id'];text='Invoice\nDoor JOD 100';d={'document_id':'qa-document','name':'invoice.pdf','page_count':1,'pages':[{'page':1,'text':text,'method':'native_pdf'}],'uncertainties':[]}
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
 with app.base.conn() as db:db.execute('UPDATE corrections SET version=2 WHERE case_id=?',(case,))
 check('old_version_stage_blocked',req('/api/integrations/v2/publish',{'run_id':'qa-report','output':output},internal)[0]==409)
 check('old_task_version_blocked',req('/api/cases/'+case+'/followup',{**change,'revision':1})[0]==409)
 code,old=req('/api/cases/'+case+'/report?version=1');check('old_report_read_only_with_correct_version',code==200 and old['version']==1 and old['is_current'] is False)
 with client.open(url+'/api/cases/'+case+'/report-print?version=1',timeout=10) as response:
  printed=response.read().decode('utf-8');check('print_keeps_requested_version_and_sources',response.status==200 and 'Door JOD 100' in printed and 'الإصدار 1' in printed)
 print('V2 HTTP checks:',len(checks))
finally:server.shutdown();server.server_close()
