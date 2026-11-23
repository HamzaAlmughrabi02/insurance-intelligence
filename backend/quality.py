"""Evidence-linked findings, never payment/coverage decisions."""
import re
from decimal import Decimal, InvalidOperation
import document_reader as reader

def financial_findings(evidence):
    items, findings = [], []
    money = re.compile(r'\b(JOD|USD|EUR|GBP|AED|SAR)\s*([\d,]+(?:\.\d{1,3})?)(?![\d.,])\b', re.I)
    for doc in evidence:
        for page in doc.get('pages', []):
            if not reader.usable_page(page):continue
            lines = page.get('text', '').splitlines()
            if re.search(r'(?im)^\s*(?:Repair Estimate and Invoice|Itemized repair estimate|Invoice|فاتورة(?:\s+إصلاح)?)\s*$',page.get('text','')):
                rows=[]
                for index,line in enumerate(lines):
                    hit=money.search(line)
                    if not hit:continue
                    label=line[:hit.start()].strip() or (lines[index-1].strip() if index else '')
                    if not label or re.search(r'\b(?:INV-|reference|date)\b',label,re.I):continue
                    rows.append({'label':label,'amount':Decimal(hit[2].replace(',','')),'currency':hit[1].upper(),'quote':label+'\n'+hit[0]})
                totals=[r for r in rows if re.fullmatch(r'TOTAL|الإجمالي|المجموع',r['label'],re.I)]
                parts=[r for r in rows if not re.search(r'total|الإجمالي|المجموع|tax|ضريبة|discount|خصم',r['label'],re.I)]
                adjustments=any(re.search(r'tax|ضريبة|discount|خصم|subtotal',r['label'],re.I) for r in rows)
                if len(totals)==1 and len(parts)>=2 and len({r['currency'] for r in parts+totals})==1 and not doc.get('uncertainties') and not adjustments:
                    total=totals[0];summed=sum(r['amount'] for r in parts)
                    if abs(summed-total['amount'])>Decimal('.01'):
                        findings.append({'code':'INVOICE_TOTAL_MISMATCH','severity':'HIGH','message':'مجموع بنود الفاتورة المقروءة يختلف عن الإجمالي المطبوع؛ راجع اكتمال القراءة والضرائب والخصومات.','source':'EVIDENCE_RULE','verification_status':'REQUIRES_REVIEW',
                            'sources':[{'document_id':doc['document_id'],'page':page['page'],'quote':page['text'][:16000]}],
                            'recorded_total':str(total['amount']),'sum_of_read_items':str(summed),'currency':total['currency']})
            for index, line in enumerate(lines):
                if not re.search(r'hood|غطاء\s*(?:المحرك|السيارة)', line, re.I):continue
                # Link amount only to this line or a directly adjacent amount-only line.
                quote=line.strip();match=money.search(quote)
                if not match and index+1<len(lines) and money.fullmatch(lines[index+1].strip()):
                    quote+='\n'+lines[index+1].strip();match=money.search(quote)
                if not match:continue
                try:amount=str(Decimal(match[2].replace(',','')))
                except InvalidOperation:continue
                item={'item':'hood','amount':amount,'currency':match[1].upper(),
                    'document_id':doc['document_id'],'page':page['page'],'quote':quote}
                if not any(x==item for x in items):items.append(item)
    if items:
        findings.append({'code':'REPAIR_ITEM_REQUIRES_VERIFICATION','severity':'MEDIUM',
            'message':'بند إصلاح غطاء المحرك يحتاج مقارنة بتقرير الحادث والفحص؛ لم يُحسم الاستحقاق.',
            'source':'EVIDENCE_RULE','verification_status':'UNVERIFIED','sources':items})
    return items,findings

def field_quality(claim, choices, corrections):
    result={}
    for key in ('policy_number','accident_date','vehicle_plate','incident_description'):
        sources=choices.get(key,[])
        status='CORRECTED' if key in corrections else 'OBSERVED' if claim.get(key) else 'CONFLICT' if sources else 'MISSING'
        result[key]={'status':status,'independently_verified':False,'sources':sources}
    return result

def supported_kind(kind):
    return 'motor' if kind in ('motor','مطالبة تأمين مركبة') else 'health' if kind in ('health','مطالبة تأمين صحي') else 'document_review'
