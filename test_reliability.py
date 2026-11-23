"""Isolated HTTP regression: upload contract, review CAS, stale callbacks and scoped agent tools."""
import sys,json,secrets,threading,urllib.request,urllib.error,http.cookiejar,io
from pathlib import Path
from unittest.mock import patch
from pypdf import PdfWriter
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'backend'))
import integration as app
import reliability
scratch=ROOT/'qa-isolated'/('reliability-'+secrets.token_hex(4))
app.base.DATA=scratch;app.base.DB=scratch/'app.sqlite3';app.base.UPLOADS=scratch/'uploads';app.init()
server=app.base.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
url='http://127.0.0.1:'+str(server.server_port)
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def req(path,body=None,raw=None,headers=None):
 h=dict(headers or {})
 if body is not None:raw=json.dumps(body).encode();h['Content-Type']='application/json'
 if 'csrf' in globals():h['X-CSRF-Token']=csrf
 try:
  with client.open(urllib.request.Request(url+path,data=raw,headers=h),timeout=10) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
passed=[]
def check(name,value):
 assert value,name
 passed.append(name);print('PASS',name)
try:
 ticket=app.auth_sessions.issue_setup_invite()
 code,session=req('/api/auth/setup',{'username':'synthetic-owner','password':secrets.token_urlsafe(24),'setup_ticket':ticket});assert code==201;csrf=session['csrf']
 code,created=req('/api/cases',{'kind':'health','client':'QA SYNTHETIC','notes':'Please process urgently'});case=created['id'];assert code==201
 writer=PdfWriter();writer.add_blank_page(width=600,height=800);buf=io.BytesIO();writer.write(buf)
 code,uploaded=req('/api/cases/'+case+'/documents',raw=buf.getvalue(),headers={'X-Filename':'scan.pdf'})
 check('real_http_upload',code==201)
 with app.base.conn() as c:doc=dict(c.execute('SELECT * FROM documents WHERE id=?',(uploaded['document_id'],)).fetchone())
 check('upload_storage_is_extensionless',Path(doc['path']).suffix=='' and Path(doc['path']).read_bytes().startswith(b'%PDF-'))
 sys.path.append(str(ROOT/'.ocr-venv/Lib/site-packages'))
 import importlib.util
 if importlib.util.find_spec('pypdfium2'):
  import document_service
  image=document_service.page_image(Path(doc['path']),1);check('actual_extensionless_pdf_render',image.width>0);image.close()
 e={'document_id':doc['id'],'name':doc['original_name'],'method':'native_pdf','uncertainties':[],'pages':[{'page':1,'text':'Policy number: POL-1\nIncident date: 18 Nov 2026\nVehicle registration: TEST-1','method':'native_pdf'}]}
 with patch.object(app,'extract',return_value=e),patch.object(app.document_reader,'request',return_value={'model':'mock','fields':[]}):payload=app.build(case,1,{})
 check('health_not_reclassified_motor',payload['claim_data']['claim_type']=='health')
 check('admin_note_not_incident_description',payload['claim_data']['incident_description']=='')
 with app.base.conn() as c:
  c.execute('INSERT INTO corrections VALUES(?,?,?)',(case,2,'{}'))
  c.execute('INSERT INTO integration_jobs(job_id,case_id,version,payload,status) VALUES(?,?,?,?,?)',('WEB-'+case+'-v1',case,1,json.dumps(payload),'failed'))
  c.execute("UPDATE cases SET status='preparing' WHERE id=?",(case,))
 code,_=req('/api/integrations/n8n/result',{'case_id':case,'job_id':'WEB-'+case+'-v1','result':{'claim_version':1,'claim_status_changed':False,'final_claim_decision':None}},headers={'Authorization':'Bearer '+app.cfg['N8N_CALLBACK_TOKEN']})
 check('old_callback_blocked_while_new_version_preparing',code==409)
 payload2={**payload,'claim_version':2,'job_id':'WEB-'+case+'-v2'}
 with app.base.conn() as c:c.execute('INSERT INTO integration_jobs(job_id,case_id,version,payload,status) VALUES(?,?,?,?,?)',(payload2['job_id'],case,2,json.dumps(payload2),'processing'))
 valid_result={'claim_version':2,'extracted':payload2['claim_data'],'evidence':payload2['evidence'],'requires_human_review':True,'final_claim_decision':None,'claim_status_changed':False}
 code,_=req('/api/integrations/n8n/result',{'case_id':case,'job_id':payload2['job_id'],'result':{**valid_result,'extracted':{'policy_number':'WRONG'}}},headers={'Authorization':'Bearer '+app.cfg['N8N_CALLBACK_TOKEN']})
 check('mismatched_result_snapshot_rejected',code==409)
 code,_=req('/api/integrations/n8n/result',{'case_id':case,'job_id':payload2['job_id'],'result':{**valid_result,'claim_status_changed':True}},headers={'Authorization':'Bearer '+app.cfg['N8N_CALLBACK_TOKEN']})
 check('callback_cannot_make_final_state_change',code==400)
 code,_=req('/api/integrations/n8n/result',{'case_id':case,'job_id':payload2['job_id'],'result':valid_result},headers={'Authorization':'Bearer '+app.cfg['N8N_CALLBACK_TOKEN']})
 check('matching_reserved_result_accepted',code==200)
 result={'claim_version':2,'extracted':{},'evidence':[e]}
 with app.base.conn() as c:c.execute("UPDATE cases SET status='review',result=? WHERE id=?",(json.dumps(result),case))
 check('stale_review_blocked',req('/api/cases/'+case+'/review',{'decision':'approve','note':'Synthetic review','version':1})[0]==409)
 code,review=req('/api/cases/'+case+'/review',{'decision':'approve','note':'Synthetic review','version':2})
 check('versioned_review_saved_with_outbox',code==200 and review['review_sync']=='pending')
 check('duplicate_review_blocked',req('/api/cases/'+case+'/review',{'decision':'approve','note':'Synthetic review','version':2})[0]==409)
 import time
 request_id='synthetic-request'
 with app.base.conn() as c:c.execute('INSERT INTO assistant_requests(id,case_id,version,question,actor,expires) VALUES(?,?,?,?,?,?)',(request_id,case,2,'policy number','QA',time.time()+60))
 hit=reliability.tool(request_id,'read_page',{'document_id':doc['id'],'page':1})
 check('agent_reads_scoped_page',hit['sources'][0]['document_id']==doc['id'])
 try:reliability.tool(request_id,'read_page',{'document_id':'OTHER-CLAIM-DOC','page':1});allowed=True
 except ValueError:allowed=False
 check('agent_cross_case_page_blocked',not allowed)
 answer=reliability.finish(request_id,{'answer':'Invented answer','citations':[{'document_id':doc['id'],'page':1,'quote':'This text was never present'}]})
 check('invented_agent_citation_rejected',answer['status']=='insufficient_evidence')
finally:server.shutdown();server.server_close()
print('Reliability HTTP checks:',len(passed))
