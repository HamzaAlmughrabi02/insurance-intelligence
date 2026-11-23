import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'backend'))
import quality,document_reader
class QualityTests(unittest.TestCase):
 def evidence(self,text):return [{'document_id':'synthetic','pages':[{'page':1,'text':text,'method':'native_pdf'}]}]
 def test_invoice_reference_is_not_a_repair_price(self):
  self.assertEqual(quality.financial_findings(self.evidence('Hood inspected. Invoice INV-850')),( [], []))
 def test_currency_is_preserved(self):
  items,findings=quality.financial_findings(self.evidence('Hood panel and paint\nUSD 850'))
  self.assertEqual(items[0]['currency'],'USD');self.assertEqual(items[0]['amount'],'850');self.assertEqual(findings[0]['sources'][0]['page'],1)
 def test_unrelated_page_amount_not_linked(self):
  self.assertFalse(quality.financial_findings(self.evidence('Hood inspected\nInvoice ID\nJOD 850'))[0])
 def test_low_confidence_cannot_bypass_via_model(self):
  self.assertFalse(document_reader.grounded_proposals({'fields':[{'field':'policy_number','value':'POL-1','quote':'Policy number: POL-1'}]},{'page':1,'text':'Policy number: POL-1','method':'paddleocr','confidence':.1}))
 def test_no_implicit_motor_type(self):
  self.assertEqual(quality.supported_kind('health'),'health');self.assertEqual(quality.supported_kind('وثيقة تأمين'),'document_review')
 def test_invoice_sum_mismatch(self):
  findings=quality.financial_findings(self.evidence('Invoice\nBumper\nJOD 100\nHeadlight\nJOD 200\nTOTAL\nJOD 400'))[1]
  self.assertTrue(any(f['code']=='INVOICE_TOTAL_MISMATCH' and f['sum_of_read_items']=='300' for f in findings))
 def test_consistent_invoice_no_sum_warning(self):
  findings=quality.financial_findings(self.evidence('Invoice\nBumper\nUSD 100\nHeadlight\nUSD 200\nTOTAL\nUSD 300'))[1]
  self.assertFalse(any(f['code']=='INVOICE_TOTAL_MISMATCH' for f in findings))
if __name__=='__main__':unittest.main()
