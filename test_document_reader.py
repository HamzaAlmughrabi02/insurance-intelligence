"""Deterministic grounding and fallback checks; no models/network/live customer data."""
import sys, unittest, tempfile, hashlib
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'backend'))
import document_reader as reader

class ReaderTests(unittest.TestCase):
    def test_scanned_page_requires_ocr(self):
        self.assertTrue(reader.needs_ocr('  '))
        self.assertFalse(reader.needs_ocr('Policy number: POL-2026-10482. Sufficient native text here.'))
    def test_arabic_digits_and_dates(self):
        self.assertEqual(reader.parse_date('٢٠٢٦-١١-١٨ :'),'2026-11-18')
        self.assertEqual(reader.parse_date('18 Nov 2026'),'2026-11-18')
        self.assertEqual(reader.parse_date('2026-02-30'),'')
    def test_mixed_arabic_ocr_fields(self):
        docs=[{'document_id':'synthetic','pages':[{'page':2,'method':'paddleocr','confidence':.95,
            'text':'رقم الوثيقة POL-2026-10482 :\nتاريخ الحادث 18-11-2026 :\nرقم المركبة TEST-4821 :'}]}]
        fields=reader.candidates(docs)
        self.assertEqual(fields['policy_number'][0]['value'],'POL-2026-10482')
        self.assertEqual(fields['accident_date'][0]['value'],'2026-11-18')
        self.assertEqual(fields['vehicle_plate'][0]['value'],'TEST-4821')
        self.assertEqual(fields['accident_date'][0]['page'],2)
    def test_low_confidence_not_used_for_fields(self):
        self.assertEqual(reader.candidates([{'document_id':'synthetic','pages':[{
            'page':1,'method':'paddleocr','confidence':.2,'text':'Policy number: INVENTED'}]}]),{})
    def test_vision_cannot_invent_quote(self):
        context={'fields':[{'field':'policy_number','value':'POL-FAKE','quote':'Policy number: POL-FAKE'}]}
        self.assertEqual(reader.grounded_proposals(context,{'page':1,'text':'Policy number: POL-REAL'}),[])
    def test_vision_cannot_relabel_invoice_as_accident_date(self):
        context={'fields':[{'field':'accident_date','value':'2026-11-18','quote':'Invoice date: 2026-11-18'}]}
        self.assertEqual(reader.grounded_proposals(context,{'page':1,'text':'Invoice date: 2026-11-18'}),[])
    def test_vision_grounded_quote(self):
        quote='Policy number: POL-REAL'
        context={'model':'local-test','fields':[{'field':'policy_number','value':'POL-REAL','quote':quote}]}
        result=reader.grounded_proposals(context,{'page':3,'text':quote,'method':'native_pdf'})
        self.assertEqual(result[0]['value'],'POL-REAL')
        self.assertEqual(result[0]['source'],'vision_grounded_quote')
        self.assertEqual(result[0]['page'],3)
    def test_unexpected_model_types_rejected(self):
        self.assertEqual(reader.grounded_proposals({'fields':[None,{'field':7,'value':{},'quote':None}]},{'page':1,'text':'test'}),[])
    def test_value_only_quote_uses_real_labeled_line(self):
        c={'fields':[{'field':'policy_number','value':'POL-REAL','quote':'POL-REAL'}]}
        result=reader.grounded_proposals(c,{'page':1,'text':'Policy ID: POL-REAL'})
        self.assertEqual(result[0]['quote'],'Policy ID: POL-REAL')
    def test_ocr_failure_preserves_original_for_review(self):
        import integration as app
        from pypdf import PdfWriter
        with tempfile.TemporaryDirectory() as scratch:
            path=Path(scratch)/'synthetic-blank.pdf'
            writer=PdfWriter();writer.add_blank_page(width=600,height=800)
            with path.open('wb') as f:writer.write(f)
            before=path.read_bytes()
            doc={'id':'synthetic','path':str(path),'original_name':path.name,'sha256':hashlib.sha256(before).hexdigest()}
            with patch.object(app.base,'UPLOADS',Path(scratch)),patch.object(reader,'request',side_effect=OSError('offline')):
                result=app.extract(doc)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(result['status'],'requires_review')
            self.assertEqual(result['pages'][0]['page'],1)
            self.assertTrue(any('OCR_UNAVAILABLE' in flag for flag in result['uncertainties']))

if __name__=='__main__':unittest.main()
