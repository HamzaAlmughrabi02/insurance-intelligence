"""Current-version projection regressions on an in-memory database."""
import json,sqlite3,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'backend'))
import workspace_api as w
class Projection(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.executescript("""CREATE TABLE cases(id,kind,client,status,created_at,review_note,result);CREATE TABLE corrections(case_id,version);CREATE TABLE report_runs(case_id,version,status,stage,created_at,report);CREATE TABLE documents(id,case_id);CREATE TABLE followup_tasks(case_id,version,state);CREATE TABLE document_roles(case_id,updated_at);CREATE TABLE audit(case_id,action,created_at);CREATE TABLE review_events(case_id,version,status);""")
  self.c.execute('INSERT INTO cases VALUES(?,?,?,?,?,?,?)',('QA','motor','Synthetic','review','2026-01-01','',None));self.c.execute('INSERT INTO corrections VALUES(?,?)',('QA',2))
  self.c.execute('INSERT INTO report_runs VALUES(?,?,?,?,?,?)',('QA',2,'completed','DONE','2026-01-02',json.dumps({'findings':[{'severity':'LOW','text':'low'},{'severity':'HIGH','text':'urgent'}],'fields':{'policy_number':'SYN-1'}})))
 def row(self):return w.rows(self.c,'QA')[0]
 def test_ready(self):
  r=self.row();self.assertTrue(r['can_approve']);self.assertEqual(r['top_reason'],'urgent');self.assertEqual(r['high_findings'],1)
 def test_tasks_scoped_to_current_version(self):
  self.c.execute('INSERT INTO followup_tasks VALUES(?,?,?)',('QA',1,'OPEN'));self.assertTrue(self.row()['can_approve'])
  self.c.execute('INSERT INTO followup_tasks VALUES(?,?,?)',('QA',2,'OPEN'));r=self.row();self.assertFalse(r['can_approve']);self.assertEqual(r['next_action'],'FOLLOWUP')
 def test_role_and_supplement_require_update(self):
  self.c.execute('INSERT INTO audit VALUES(?,?,?)',('QA','supplement_uploaded','2026-01-03'));r=self.row();self.assertFalse(r['can_approve']);self.assertEqual(r['next_action'],'UPDATE_REPORT')
 def test_reserved_version_does_not_reuse_ready_report(self):
  self.c.execute('UPDATE corrections SET version=3');r=self.row();self.assertFalse(r['can_approve']);self.assertEqual(r['display_status'],'REPORT_PENDING');self.assertEqual(r['top_reason'],'')
 def test_recorded_review_not_offered_again(self):
  self.c.execute("UPDATE cases SET status='approved'");self.assertEqual(self.row()['next_action'],'VIEW_REVIEW');self.assertFalse(self.row()['can_approve'])
 def test_missing_case(self):self.assertEqual(w.rows(self.c,'missing'),[])
if __name__=='__main__':unittest.main()
