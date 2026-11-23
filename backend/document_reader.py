"""Lightweight integration client; OCR and model dependencies stay in a separate process."""
import json, re, unicodedata, urllib.request, os
from urllib.parse import urlsplit
from datetime import datetime

def request(operation, document_id, page, token, **extra):
    body = dict(document_id=document_id, page=page, **extra)
    url=os.environ.get('INSURANCE_READER_URL','http://127.0.0.1:8787')
    if urlsplit(url).hostname not in ('127.0.0.1','localhost'):raise ValueError('Reader must be local')
    req = urllib.request.Request(url+'/' + operation,
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.load(response)

def normalize(text):
    text = unicodedata.normalize('NFKC', str(text))
    text = text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
    return re.sub(r'\s+', ' ', text).strip()

def needs_ocr(text):
    return sum(c.isalnum() for c in text) < 30 or '\ufffd' in text

def usable_page(page):
    return page.get('method') != 'paddleocr' or page.get('confidence', 0) >= .8

def page_has_images(page):
    def scan(resources,depth=0):
        if not resources or depth>3:return False
        resources=resources.get_object();objects=resources.get('/XObject')
        objects=objects.get_object() if objects else {}
        for ref in objects.values():
            obj=ref.get_object()
            if str(obj.get('/Subtype'))=='/Image' and int(obj.get('/Width',0))*int(obj.get('/Height',0))>100000:return True
            if str(obj.get('/Subtype'))=='/Form' and scan(obj.get('/Resources'),depth+1):return True
        return False
    return scan(page.get('/Resources'))

def parse_date(value):
    value = normalize(value).strip(' :：')
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%d-%m-%Y', '%d %b %Y', '%d %B %Y'):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return ''

def valid_field_value(field,value):
    value=normalize(value)
    if field=='policy_number':
        return bool(re.fullmatch(r'[A-Za-z\u0600-\u06ff0-9][A-Za-z\u0600-\u06ff0-9/_-]{2,79}',value) and (re.search(r'\d',value) or re.fullmatch(r'[A-Z]{2,12}[-/_][A-Z0-9/_-]{2,60}',value)))
    if field=='vehicle_plate':
        return bool(2<=len(value)<=20 and re.search(r'\d',value) and re.fullmatch(r'[A-Za-z\u0600-\u06ff0-9 -]+',value) and not re.search(r'\bVIN\b|insured|policy|vehicle|toyota|coverage',value,re.I))
    return bool(value)

def candidates(evidence):
    result = {}
    patterns = {
        'policy_number': r'(?:Policy\s*(?:number|no\.?|#)|رقم\s*(?:وثيقة\s*التأمين|الوثيقة|البوليصة))\s*[:：#\-]?\s*([^\n:：]{2,80})',
        'accident_date': r'(?:Incident date|Date of incident|Accident date|تاريخ\s*(?:الحادث|وقوع الحادث))\s*[:：]?\s*([^\n]{6,40})',
        'vehicle_plate': r'(?:Vehicle registration|Registration|License plate|رقم\s*(?:المركبة|اللوحة))\s*[:：]?\s*([^\n]{2,40})',
        'incident_description': r'(?:Claimant statement|Incident description|وصف\s*الحادث|تفاصيل\s*الحادث)\s*[:：]?\s*([^\n]{5,1000})'}
    for doc in evidence:
        for page in doc.get('pages', []):
            if not usable_page(page):
                continue
            text = unicodedata.normalize('NFKC', page.get('text', ''))
            reversed_patterns={
                'policy_number':r'([A-Za-z\u0600-\u06ff0-9/_-]{3,80})[ \t]+(?:Policy[ \t]*(?:number|no\.?|#)|رقم[ \t]*(?:الوثيقة|البوليصة))',
                'vehicle_plate':r'([^\n:：]{2,40})[ \t]+(?:Vehicle registration|Registration|License plate|رقم[ \t]*(?:المركبة|اللوحة))',
                'accident_date':r'([^\n]{6,40})[ \t]+(?:Incident date|Date of incident|Accident date|تاريخ[ \t]*الحادث)'}
            for field, pattern in patterns.items():
                matches=[(m,'label_match') for m in re.finditer(pattern,text,re.I)]
                if field in reversed_patterns:matches.extend((m,'reverse_label_match') for m in re.finditer(reversed_patterns[field],text,re.I))
                for match,source in matches:
                    printed = match.group(1).strip(' :：\t\r\n')
                    value = parse_date(printed) if field == 'accident_date' else printed
                    if not value or not valid_field_value(field,value):
                        continue
                    result.setdefault(field, []).append({'value': value, 'quote': match.group(0).strip(),
                        'printed_value': printed, 'document_id': doc['document_id'], 'page': page['page'],
                        'method': page.get('method', doc.get('method')), 'source': source})
    return result

def grounded_proposals(context, page):
    """A model proposal can only fill a claim field when quote and value match extracted evidence."""
    if not usable_page(page):
        return []
    text = normalize(page.get('text', ''))
    accepted = []
    for item in context.get('fields', []):
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) for k in ('field', 'value', 'quote')):
            continue
        field, value, quote = item['field'], normalize(item['value']), normalize(item['quote'])
        if not value or len(value) > 1000 or len(quote) < 8 or quote not in text or value not in quote:
            continue
        if field not in ('policy_number', 'accident_date', 'vehicle_plate', 'incident_description'):
            continue
        labels = {'policy_number': r'policy|وثيقة|الوثيقة|بوليصة|البوليصة',
            'vehicle_plate': r'registration|plate|المركبة|اللوحة',
            'incident_description': r'claimant|incident|الحادث|إفادة',
            'accident_date': r'incident|accident|الحادث'}
        if not re.search(labels[field], quote, re.I):
            # Some local models quote the value only. Extend from actual extracted lines,
            # never from a generated label, and reject ambiguous/no-label matches.
            lines = [line.strip() for line in page.get('text', '').splitlines()
                if value in normalize(line) and re.search(labels[field], normalize(line), re.I)]
            lines = list(dict.fromkeys(lines))
            if len(lines) != 1:
                continue
            quote = normalize(lines[0])
        # Require an appropriate label even when a model suggests the field.
        if field == 'accident_date' and not re.search(r'incident|accident|الحادث', quote, re.I):
            continue
        final = parse_date(value) if field == 'accident_date' else item['value'].strip()
        if final and valid_field_value(field,final):
            accepted.append(dict(field=field, value=final, printed_value=item['value'], quote=quote,
                page=page['page'], method=page.get('method'), source='vision_grounded_quote', model=context.get('model')))
    return accepted
