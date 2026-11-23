"""Read-only UI projection of the current case/report/task state. No decision writes."""
import json
import report_engine
BASE=None
def configure(base):
 global BASE
 BASE=base
def rows(c,case_id=None):
 sql='''SELECT c.id,c.kind,c.client,c.status,c.created_at,c.review_note,
 COALESCE(v.version,0) AS current_version,r.status AS report_status,r.stage AS report_stage,r.created_at AS report_created,
 json_extract(r.report,'$.findings') AS findings,json_extract(r.report,'$.quality_state') AS quality_state,
 COALESCE(json_extract(r.report,'$.fields.policy_number'),json_extract(c.result,'$.extracted.policy_number')) AS policy_number,
 (SELECT COUNT(*) FROM documents d WHERE d.case_id=c.id) AS document_count,
 (SELECT COUNT(*) FROM followup_tasks t WHERE t.case_id=c.id AND t.version=v.version AND t.state IN ('OPEN','IN_PROGRESS')) AS pending_tasks,
 (SELECT MAX(updated_at) FROM document_roles d WHERE d.case_id=c.id) AS role_updated,
 (SELECT MAX(created_at) FROM audit a WHERE a.case_id=c.id AND a.action='supplement_uploaded') AS supplement_updated,
 (SELECT status FROM review_events e WHERE e.case_id=c.id AND e.version=v.version ORDER BY rowid DESC LIMIT 1) AS review_sync
 FROM cases c LEFT JOIN corrections v ON v.case_id=c.id
 LEFT JOIN report_runs r ON r.case_id=c.id AND r.version=v.version'''
 if case_id is not None:sql+=' WHERE c.id=?'
 sql+=' ORDER BY c.created_at DESC'
 result=[]
 for row in c.execute(sql,(case_id,) if case_id is not None else ()):
  item=dict(row)
  try:findings=json.loads(item.pop('findings') or '[]')
  except (ValueError,TypeError):findings=[]
  ordered=sorted((f for f in findings if isinstance(f,dict)),key=lambda f:{'HIGH':0,'MEDIUM':1,'LOW':2}.get(f.get('severity'),3))
  top=ordered[0] if ordered else None
  text=(top or {}).get('text','')
  for key,label in report_engine.FIELD_LABELS.items():text=text.replace(key,label)
  changed=max(item.pop('role_updated') or '',item.pop('supplement_updated') or '')
  item['report_outdated']=bool(item['report_created'] and changed>item['report_created'])
  item['top_reason']=text;item['high_findings']=sum(f.get('severity')=='HIGH' for f in ordered)
  state=item['status'];report_ready=item['report_status']=='completed'
  if state=='draft':display='DRAFT';action='CONTINUE_DRAFT'
  elif state=='failed':display='FAILED';action='RETRY_PROCESSING'
  elif state in ('preparing','queued','processing'):display=state.upper();action='WAIT'
  elif state in ('approved','rejected'):display='REVIEW_RECORDED';action='VIEW_REVIEW'
  elif not report_ready:display='REPORT_PENDING';action='WAIT'
  elif item['report_outdated']:display='UPDATE_REQUIRED';action='UPDATE_REPORT'
  elif item['pending_tasks']:display='FOLLOWUP_REQUIRED';action='FOLLOWUP'
  else:display='READY_FOR_REVIEW';action='RECORD_REVIEW'
  item['display_status']=display;item['next_action']=action
  item['can_approve']=state=='review' and report_ready and not item['pending_tasks'] and not item['report_outdated']
  item['can_record_nonapproval']=state=='review' and report_ready
  result.append(item)
 return result

class WorkspaceMixin:
 def do_GET(self):
  p=BASE.urlparse(self.path).path
  if p=='/api/workspace/cases' or (p.startswith('/api/workspace/cases/') and p.endswith('/state')):
   if not self.auth():return
   case=None if p=='/api/workspace/cases' else p.split('/')[4]
   with BASE.conn() as c:data=rows(c,case)
   if case and not data:return self.fail(404,'Case not found')
   return self.reply(200,data[0] if case else {'items':data,'updated_at':BASE.now()})
  return super().do_GET()
