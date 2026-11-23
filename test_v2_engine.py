"""Evidence gate and arithmetic tests with explicit reference outcomes, no model judge."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'backend'))
import report_engine as e
def doc(id,name,text,count=1,**page):return {'document_id':id,'name':name,'sha256':id*16,'page_count':count,'uncertainties':[],'pages':[{'page':1,'text':text,'method':'native_pdf',**page}]}
def report(docs):return e.prepare('QA',1,{'evidence':docs})
class Tests(unittest.TestCase):
 def test_coverage_never_invents_unknown_pages(self):
  r=report([doc('a','policy.pdf','Policy number POL-1',None)])
  self.assertFalse(r['coverage']['complete']);self.assertEqual(r['coverage']['documents'][0]['expected_pages'],None)
 def test_partial_page_cannot_claim_complete(self):
  r=report([doc('a','scan.pdf','Read header',read_flags=['OCR_PAGE_LIMIT'])]);self.assertFalse(r['coverage']['complete'])
 def test_low_quality_not_model_evidence(self):
  r=report([doc('a','scan.pdf','Amount JOD 100',method='paddleocr',confidence=.4)]);self.assertEqual(e.analyst_packet(r)['sources'],[])
 def test_every_source_matches_original_offsets(self):
  d=doc('a','invoice.pdf','Invoice\nDoor JOD 100\nHood JOD 20\nTOTAL JOD 120');r=report([d]);text=d['pages'][0]['text']
  for s in r['sources'].values():self.assertEqual(text[s['start']:s['end']],s['quote'])
 def test_generic_parts_not_only_hood(self):
  r=report([doc('a','invoice.pdf','Invoice\nDoor JOD 100'),doc('b','inspection.pdf','Inspection report\nNo door damage')]);self.assertTrue(any(f['code']=='DAMAGE_CONTEXT_REVIEW' and f['checks']['topic']=='door' for f in r['findings']))
 def test_absence_not_denial(self):
  r=report([doc('a','invoice.pdf','Invoice\nHood JOD 100'),doc('b','inspection.pdf','Inspection\nBumper damaged')]);f=next(f for f in r['findings'] if f['code']=='DAMAGE_CONTEXT_REVIEW');self.assertTrue(f['checks']['absence_is_not_denial'])
 def test_unknown_role_produces_completeness_task(self):
  r=report([doc('a','notes.pdf','Short note')]);self.assertEqual(len([t for t in r['tasks'] if t['kind']=='MISSING_DOCUMENT']),5)
 def test_reviewer_role_overrides_suggestion(self):
  r=e.prepare('QA',1,{'evidence':[doc('a','notes.pdf','Short note')]},{'a':'inspection'});self.assertEqual(r['documents'][0]['role_origin'],'REVIEWER')
 def test_arithmetic_tax_and_discount(self):
  r=report([doc('a','invoice.pdf','Invoice\nDoor JOD 100\nHood JOD 20\nTax JOD 12\nDiscount JOD 2\nTOTAL JOD 130')]);f=next(f for f in r['findings'] if f['code']=='INVOICE_ARITHMETIC_MATCH');self.assertEqual(f['checks']['computed'],'130')
 def test_arithmetic_difference(self):
  r=report([doc('a','invoice.pdf','Invoice\nDoor JOD 100\nHood JOD 20\nTOTAL JOD 200')]);self.assertTrue(any(f['code']=='INVOICE_ARITHMETIC_DIFFERENCE' for f in r['findings']))
 def test_currencies_not_combined(self):
  r=report([doc('a','invoice.pdf','Invoice\nDoor USD 100\nHood JOD 20\nTOTAL JOD 120')]);self.assertFalse(any(f['code']=='INVOICE_ARITHMETIC_MATCH' for f in r['findings']))
 def test_ambiguous_table_not_summed(self):
  r=report([doc('a','invoice.pdf','Invoice\nDoor USD 10 USD 100\nHood USD 20\nTOTAL USD 120')]);self.assertFalse(any(f['code']=='INVOICE_ARITHMETIC_MATCH' for f in r['findings']))
 def test_explicit_quantity_unit_total(self):
  r=report([doc('a','invoice.pdf','Invoice\nDoor | 2 | JOD 10 | JOD 25\nHood JOD 20\nTOTAL JOD 45')]);self.assertTrue(any(f['code']=='LINE_MULTIPLICATION_DIFFERENCE' for f in r['findings']));self.assertEqual(r['invoice_rows'][0]['quantity'],'2')
 def proposal(self,text='ورد مبلغ JOD 100 في المستند.'):
  r=report([doc('a','invoice.pdf','Invoice\nDoor JOD 100')]);id=next(iter(r['sources']));p,w=e.proposals(r,{'observations':[{'text':text,'kind':'DOCUMENT_STATEMENT','evidence_ids':[id]}]},set(r['sources']));return r,p,w
 def test_unknown_citation_rejected(self):
  r,p,w=self.proposal();out,rejected=e.proposals(r,{'observations':[{'text':'رقم 100','kind':'DOCUMENT_STATEMENT','evidence_ids':['foreign']}]},set(r['sources']));self.assertFalse(out);self.assertTrue(rejected)
 def test_fabricated_numeric_value_blocked(self):self.assertFalse(self.proposal('ورد مبلغ 9000')[1])
 def test_decision_blocked(self):self.assertFalse(self.proposal('المطالبة مقبولة')[1])
 def test_absence_from_selected_context_blocked(self):self.assertFalse(self.proposal('لم يرد ضرر في المستند')[1])
 def test_same_doc_not_cross_doc_difference(self):
  r,p,w=self.proposal();out,_=e.proposals(r,{'observations':[{'text':'اختلاف في المبلغ','kind':'REPORTED_DIFFERENCE','evidence_ids':[p[0]['evidence_ids'][0]]}]},set(r['sources']));self.assertFalse(out)
 def test_valid_quote_does_not_bypass_semantic_rejection(self):
  r,p,w=self.proposal();a=p[0];e.gate(r,p,{'reviews':[{'assertion_id':a['assertion_id'],'status':'INSUFFICIENT','reason':'الاقتباس لا يثبت الجملة','evidence_ids':a['evidence_ids']}]});self.assertEqual(r['model_assertions'],[]);self.assertTrue(r['withheld'])
 def test_missing_review_is_withheld(self):
  r,p,w=self.proposal();e.gate(r,p,{'reviews':[]});self.assertFalse(r['model_assertions']);self.assertTrue(r['withheld'])
 def test_every_statement_needs_its_own_review(self):
  r,p,w=self.proposal('Door JOD 100');other={**p[0],'assertion_id':'second','text':'اقتراح آخر'};e.gate(r,p+[other],{'reviews':[{'assertion_id':p[0]['assertion_id'],'status':'SUPPORTED','reason':'مطابق للمقطع الأصلي','evidence_ids':p[0]['evidence_ids']}]});self.assertEqual(len(r['model_assertions']),1);self.assertEqual(len(r['withheld']),1)
 def test_two_model_agreement_cannot_publish_wrong_paraphrase(self):
  r,p,w=self.proposal('الضرائب تبلغ 100');a=p[0];e.gate(r,p,{'reviews':[{'assertion_id':a['assertion_id'],'status':'SUPPORTED','reason':'موافق','evidence_ids':a['evidence_ids']}]});self.assertFalse(r['model_assertions']);self.assertEqual(r['withheld'][0]['status'],'REQUIRES_HUMAN_CONFIRMATION')
 def test_repeating_assertion_is_not_independent_audit(self):
  r,p,w=self.proposal('Door JOD 100');a=p[0];e.gate(r,p,{'reviews':[{'assertion_id':a['assertion_id'],'status':'SUPPORTED','reason':a['text'],'evidence_ids':a['evidence_ids']}]});self.assertFalse(r['model_assertions'])
 def test_duplicated_or_malformed_review_not_accepted(self):
  r,p,w=self.proposal();item={'assertion_id':p[0]['assertion_id'],'status':'SUPPORTED','reason':'مدعوم','evidence_ids':[{}]};e.gate(r,p,{'reviews':[item]});self.assertFalse(r['model_assertions'])
 def test_same_quote_other_version_separate_report_scope(self):
  d=doc('a','invoice.pdf','Invoice\nDoor JOD 100');r=e.prepare('QA',2,{'evidence':[d]});self.assertEqual(r['claim_version'],2)
 def test_correction_is_compared_against_document_values(self):
  d=doc('a','policy.pdf','Registration TEST-1');r=e.prepare('QA',2,{'evidence':[d],'extracted':{'vehicle_plate':'TEST-2'},'field_quality':{'vehicle_plate':{'status':'CORRECTED','sources':[{'document_id':'a','page':1,'value':'TEST-1','quote':'Registration TEST-1'}]}}});self.assertTrue(any(f['code']=='CORRECTION_DIFFERS_FROM_DOCUMENTS' for f in r['findings']));self.assertTrue(any(t['kind']=='CLARIFICATION' for t in r['tasks']))
 def test_reverse_ocr_policy_label_does_not_capture_person_name(self):
  r=e.document_reader.candidates([doc('a','scan.pdf','POL-2026-10482 Policy number\nInsured Omar Khaled Mansour\nRegistration TEST-4821')]);self.assertEqual({x['value'] for x in r['policy_number']},{'POL-2026-10482'})
 def test_missing_identifier_does_not_take_next_label(self):
  r=e.document_reader.candidates([doc('a','scan.pdf','Policy number\nInsured Omar Khaled Mansour')]);self.assertFalse(r.get('policy_number'))
 def test_model_cannot_bypass_identifier_shape(self):
  page={'page':1,'text':'Policy number: Insured Omar Khaled Mansour','method':'native_pdf'};self.assertFalse(e.document_reader.grounded_proposals({'fields':[{'field':'policy_number','value':'Insured Omar Khaled Mansour','quote':page['text']}]},page))
if __name__=='__main__':unittest.main()
