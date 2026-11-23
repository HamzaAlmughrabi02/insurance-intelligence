"""Exercise account/session security on isolated synthetic data, never the real account."""
import http.cookiejar,json,secrets,sqlite3,sys,tempfile,threading,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'backend'))
import integration as app
scratch=ROOT/'qa-isolated'/('auth-'+secrets.token_hex(4))
app.base.DATA=scratch;app.base.DB=scratch/'app.sqlite3';app.base.UPLOADS=scratch/'uploads'
app.init()
server=app.base.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}'
checks=[]
def client():
 jar=http.cookiejar.CookieJar();return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)),jar
owner,jar=client();anonymous,_=client()
def req(path,method='GET',body=None,opener=owner,csrf=None,headers=None,raw=None):
 h=dict(headers or {})
 if body is not None:h['Content-Type']='application/json';raw=json.dumps(body).encode()
 if csrf:h['X-CSRF-Token']=csrf
 try:
  with opener.open(urllib.request.Request(url+path,data=raw,method=method,headers=h),timeout=20) as r:return r.status,r.headers,r.read()
 except urllib.error.HTTPError as e:return e.code,e.headers,e.read()
def check(name,passed):
 checks.append({'test':name,'status':'PASS' if passed else 'FAIL'});print(checks[-1],flush=True);assert passed,name
password=secrets.token_urlsafe(24)
try:
 check('anonymous_cases_blocked',req('/api/cases',opener=anonymous)[0]==401)
 check('legacy_api_key_not_browser_login',req('/api/cases',opener=anonymous,headers={'Authorization':'Bearer '+app.cfg['INSURANCE_API_TOKEN'],'X-Role':'supervisor'})[0]==401)
 check('first_run_requires_invitation',req('/api/auth/setup','POST',{'username':'qa-owner','password':password},opener=anonymous)[0]==403)
 ticket=app.auth_sessions.issue_setup_invite()
 code,headers,data=req('/api/auth/setup','POST',{'username':'qa-owner','password':password,'remember':True,'setup_ticket':ticket})
 session=json.loads(data);csrf=session['csrf']
 check('first_account_created',code==201 and session['user']['role']=='admin')
 cookie=headers['Set-Cookie']
 check('persistent_httponly_samesite_cookie',all(s in cookie for s in ['HttpOnly','SameSite=Strict','Max-Age=2592000']))
 with app.base.conn() as c:
  user=dict(c.execute('SELECT * FROM local_users').fetchone());stored=list(c.execute('SELECT token_hash FROM browser_sessions'))[0][0]
 check('password_argon2id_hashed',user['password_hash'].startswith('$argon2id$') and password not in user['password_hash'])
 check('session_token_hashed_at_rest',stored not in cookie and len(stored)==64)
 check('session_restores_without_api_key',req('/api/auth/session')[0]==200)
 check('setup_cannot_replace_account',req('/api/auth/setup','POST',{'username':'other','password':password,'setup_ticket':ticket},opener=anonymous)[0]==409)
 check('csrf_required_for_writes',req('/api/cases','POST',{'kind':'motor','client':'QA ACCOUNT'})[0]==403)
 code,_,data=req('/api/cases','POST',{'kind':'motor','client':'QA ACCOUNT'},csrf=csrf);case=json.loads(data)['id']
 check('authenticated_case_created',code==201)
 check('cross_origin_write_rejected',req('/api/cases','POST',{'kind':'motor','client':'QA'},csrf=csrf,headers={'Origin':'http://untrusted.invalid'})[0]==403)
 check('rebound_host_rejected',req('/api/cases',headers={'Host':'untrusted.invalid'})[0]==403)
 code,_,data=req('/api/cases/'+case+'/documents','POST',csrf=csrf,raw=b'%PDF-1.4\nsynthetic',headers={'X-Filename':'qa.pdf'})
 doc=json.loads(data)['document_id'];check('cookie_authenticated_upload',code==201)
 check('cookie_authenticated_download',req('/api/documents/'+doc)[0]==200)
 code,headers,_=req('/api/documents/'+doc+'?view=1')
 check('authenticated_inline_pdf_preview',code==200 and headers['Content-Disposition'].startswith('inline') and headers['X-Frame-Options']=='SAMEORIGIN')
 check('inline_pdf_csp_same_origin_only',"frame-ancestors 'self'" in headers['Content-Security-Policy'])
 check('inline_preview_unauthorized_blocked',req('/api/documents/'+doc+'?view=1',opener=anonymous)[0]==401)
 check('anonymous_document_blocked',req('/api/documents/'+doc,opener=anonymous)[0]==401)
 with app.base.conn() as c:actor=c.execute("SELECT actor FROM audit WHERE action='created' AND case_id=?",(case,)).fetchone()[0]
 check('audit_uses_account_identity',actor=='qa-owner')

 # Preparing is durable and does not block the upload request while OCR/model work runs.
 code,_,data=req('/api/cases/'+case+'/submit','POST',{},csrf=csrf)
 check('submit_returns_background_preparation',code==202 and json.loads(data)['status']=='preparing')
 check('duplicate_submit_during_preparation_blocked',req('/api/cases/'+case+'/submit','POST',{},csrf=csrf)[0]==409)
 with app.base.conn() as c:
  task=dict(c.execute('SELECT * FROM document_preparations WHERE case_id=?',(case,)).fetchone())
  c.execute("UPDATE document_preparations SET status='running' WHERE case_id=?",(case,))
 app.recover()
 with app.base.conn() as c:state=c.execute('SELECT status FROM document_preparations WHERE case_id=?',(case,)).fetchone()[0]
 check('interrupted_preparation_requeued',state=='queued')
 from unittest.mock import patch
 with patch.object(app,'build',return_value={'job_id':'WEB-'+case+'-v1','case_id':case}):app.prepare_pending_once()
 with app.base.conn() as c:
  job=c.execute('SELECT status FROM integration_jobs WHERE case_id=?',(case,)).fetchone()
  state=c.execute('SELECT status FROM cases WHERE id=?',(case,)).fetchone()[0]
 check('prepared_job_queued_once',job['status']=='queued' and state=='queued')

 with app.base.conn() as c:c.execute("UPDATE cases SET status='review',result=? WHERE id=?",(json.dumps({'extracted':{'policy_number':'POL-QA'},'flags':['HOOD_REPAIR_JOD_850_UNCERTAIN'],'claim_version':2}),case))
 code,_,data=req('/api/review-queue');queue=json.loads(data)
 check('review_queue_identifies_client_and_reason',code==200 and queue[0]['id']==case and queue[0]['client']=='QA ACCOUNT' and queue[0]['policy_number']=='POL-QA' and queue[0]['document_count']==1 and len(queue[0]['reasons'])==1)
 check('review_queue_requires_login',req('/api/review-queue',opener=anonymous)[0]==401)

 # Stop and restart the HTTP process abstraction; SQLite session must remain valid.
 port=server.server_port;server.shutdown();server.server_close()
 server=app.base.ThreadingHTTPServer(('127.0.0.1',port),app.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 check('session_survives_server_restart',req('/api/auth/session')[0]==200)
 check('logout_accepted',req('/api/auth/logout','POST',{},csrf=csrf)[0]==200)
 check('logout_revokes_session',req('/api/auth/session')[0]==401)
 code,_,data=req('/api/auth/login','POST',{'username':'qa-owner','password':password,'remember':False});csrf=json.loads(data)['csrf']
 check('password_login_works',code==200)
 # Server role wins over client-supplied X-Role.
 with app.base.conn() as c:c.execute('INSERT INTO local_users(username,password_hash,role,created_at) VALUES(?,?,?,?)',('qa-operator',app.auth_sessions.PASSWORDS.hash(password),'operator',app.base.now()))
 operator,_=client();_,_,data=req('/api/auth/login','POST',{'username':'qa-operator','password':password},opener=operator);opcsrf=json.loads(data)['csrf']
 check('role_header_cannot_escalate',req('/api/cases/'+case+'/reanalyze','POST',{'note':'Synthetic','fields':{}},opener=operator,csrf=opcsrf,headers={'X-Role':'supervisor'})[0]==403)
 with app.base.conn() as c:c.execute('UPDATE browser_sessions SET expires=0 WHERE user_id=?',(user['id'],))
 check('expired_session_rejected',req('/api/auth/session')[0]==401)
 for _ in range(5):req('/api/auth/login','POST',{'username':'qa-owner','password':'wrong-synthetic-password'},opener=anonymous)
 check('bruteforce_throttled',req('/api/auth/login','POST',{'username':'qa-owner','password':password},opener=anonymous)[0]==429)
 check('integration_callback_still_requires_internal_secret',req('/api/integrations/n8n/result','POST',{},opener=anonymous)[0]==401)
 check('integration_secret_independent_from_user_session',req('/api/integrations/n8n/result','POST',{},opener=anonymous,headers={'Authorization':'Bearer '+app.cfg['N8N_CALLBACK_TOKEN']})[0]==400)
finally:server.shutdown();server.server_close()
(ROOT/'account-test-results.json').write_text(json.dumps({'isolated':True,'real_account_created':False,'tests':checks},indent=2))
print('Account checks passed:',len(checks))
