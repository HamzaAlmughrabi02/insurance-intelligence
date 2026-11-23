"""Source-addressed V2 reports. Code checks and model judgements remain distinct."""
import hashlib,json,re,unicodedata
from decimal import Decimal
import document_reader

VERSION='2.0.2'
ROLES={'policy':'وثيقة التأمين','claim_form':'نموذج المطالبة','incident':'تقرير الحادث','inspection':'تقرير الفحص','invoice':'فاتورة الإصلاح'}
FIELD_LABELS={'policy_number':'رقم الوثيقة','vehicle_plate':'رقم المركبة','accident_date':'تاريخ الحادث','incident_description':'وصف الحادث'}
ROLE_PATTERNS={'policy':r'\bpolicy\b|وثيقة|بوليصة','claim_form':r'claim.?form|نموذج.*مطالبة','incident':r'incident|accident.?report|تقرير.*حادث','inspection':r'inspection|تقرير.*فحص','invoice':r'invoice|repair.?estimate|فاتورة'}
PARTS={'hood':('غطاء المحرك',r'\bhood\b|غطاء\s*المحرك'),'bumper':('الصدام',r'\bbumper\b|الصدام|مصد'),'headlight':('المصباح',r'\bheadlights?\b|مصباح|مصابيح'),'door':('الباب',r'\bdoors?\b|باب|أبواب'),'windshield':('الزجاج الأمامي',r'\bwindshield\b|الزجاج\s*الأمامي'),'fender':('الرفرف',r'\bfender\b|رفرف'),'roof':('السقف',r'\broof\b|سقف'),'trunk':('الصندوق الخلفي',r'\btrunk\b|الصندوق\s*الخلفي')}
MONEY=re.compile(r'\b(JOD|USD|EUR|GBP|AED|SAR)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,3})?)(?![\d.,])\b',re.I)

def norm(s):return document_reader.normalize(s).casefold()
def uid(*values):return hashlib.sha256(json.dumps(values,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:24]
def role(name,text=''):
 hits=[key for key,pattern in ROLE_PATTERNS.items() if re.search(pattern,name,re.I)]
 if len(hits)!=1:hits=[key for key,pattern in ROLE_PATTERNS.items() if re.search(pattern,text[:180],re.I)]
 return hits[0] if len(hits)==1 else 'unknown'

def prepare(case_id,version,result,roles=None):
 roles=roles or {};sources={};documents=[];coverage=[];comparisons=[];findings=[];invoices=[]
 def addsource(doc,p,quote,start=None):
  text=p.get('text','');start=text.find(quote) if start is None else start
  if start<0 or text[start:start+len(quote)]!=quote:return None
  key=uid(doc['document_id'],str(p['page']),doc.get('sha256'),quote,start)
  sources[key]={'evidence_id':key,'document_id':doc['document_id'],'document_name':doc['name'],'document_sha256':doc.get('sha256'),'page':p['page'],'start':start,'end':start+len(quote),'quote':quote,'context':text[max(0,start-300):start+len(quote)+300],'method':p.get('method',doc.get('method')),'readable':document_reader.usable_page(p) and bool(text.strip()),'confidence':p.get('confidence'),'blocks':[b for b in p.get('blocks',[]) if b.get('text') and b['text'] in quote]}
  return key
 for doc in result.get('evidence',[]):
  pages=doc.get('pages',[]);assigned=roles.get(doc['document_id']);kind=assigned or role(doc['name'],'\n'.join(p.get('text','') for p in pages)[:180])
  documents.append({'id':doc['document_id'],'name':doc['name'],'role':kind,'role_origin':'REVIEWER' if assigned else 'SUGGESTED','sha256':doc.get('sha256')})
  expected=doc.get('page_count');rows=[]
  for p in pages:
   text=p.get('text','');flags=p.get('read_flags',[])
   status='UNREADABLE' if not text.strip() else 'LOW_QUALITY' if not document_reader.usable_page(p) else 'PARTIAL' if flags else 'READ'
   # Legacy extraction flags do not identify every affected page; remain conservative.
   if status=='READ' and any(x.startswith(('TEXT_TRUNCATED','OCR_PAGE_LIMIT','OCR_UNAVAILABLE')) for x in doc.get('uncertainties',[])):status='PARTIAL'
   rows.append({'page':p['page'],'status':status,'method':p.get('method',doc.get('method')),'flags':flags,'characters':len(text),'confidence':p.get('confidence')})
   # Store addressable paragraphs with surrounding context, not detached search hits.
   for match in re.finditer(r'[^\n]+(?:\n[^\n]+){0,3}',text):
    quote=match[0][:1200]
    if quote.strip():addsource(doc,p,quote,match.start())
  complete=expected is not None and len(rows)==expected and all(r['status']=='READ' for r in rows)
  coverage.append({'document_id':doc['document_id'],'name':doc['name'],'expected_pages':expected,'observed_pages':len(rows),'complete':complete,'pages':rows,'warnings':doc.get('uncertainties',[])})
  for part,(label,pattern) in PARTS.items():
   mentions=[]
   for p in pages:
    for line in p.get('text','').splitlines():
     if not re.search(pattern,line,re.I):continue
     neg=bool(re.search(r'\b(?:no|not|without|undamaged)\b|لا\s*يوجد|لم\s*يتضرر|سليم',line,re.I))
     ev=addsource(doc,p,line)
     if ev:mentions.append({'evidence_id':ev,'polarity':'NEGATIVE_TEXT' if neg else 'MENTIONED','text':line,'readable':sources[ev]['readable']})
   comparisons.append({'topic':part,'label':label,'document_id':doc['document_id'],'role':kind,'status':'AMBIGUOUS' if len({m['polarity'] for m in mentions})>1 else mentions[0]['polarity'] if mentions else 'NOT_MENTIONED_IN_READ_TEXT' if complete else 'INSUFFICIENT_READING','evidence_ids':[m['evidence_id'] for m in mentions],'interpretation':'ذكر أو نفي لفظي يحتاج قراءة السياق؛ لا يثبت وحده الضرر أو عدمه.'})
  if kind=='invoice':
   for p in pages:invoices.extend(invoice_rows(doc,p,addsource,sources,findings))
 # Field comparison uses all extracted candidates, including conflicting candidates.
 for field,quality in result.get('field_quality',{}).items():
  values=[]
  for s in quality.get('sources',[]):
   doc=next((d for d in result.get('evidence',[]) if d['document_id']==s.get('document_id')),None)
   page=next((p for p in doc.get('pages',[]) if str(p['page'])==str(s.get('page'))),None) if doc else None
   if not page or not s.get('quote'):continue
   ev=addsource(doc,page,s['quote'])
   if ev:values.append({'value':s.get('value'),'evidence_id':ev,'document_id':doc['document_id']})
  if len({norm(v['value']) for v in values})>1:
   findings.append(finding('FIELD_CONFLICT','HIGH','توجد قيم مختلفة لحقل '+FIELD_LABELS.get(field,field),[v['evidence_id'] for v in values],{'field':field,'values':values}))
  effective=result.get('extracted',{}).get(field)
  if quality.get('status')=='CORRECTED' and values and norm(effective) not in {norm(v['value']) for v in values}:
   findings.append(finding('CORRECTION_DIFFERS_FROM_DOCUMENTS','HIGH','تصحيح المراجع لحقل '+FIELD_LABELS.get(field,field)+' يختلف عن القيم المقروءة من المستندات؛ راجع سبب التصحيح.',[v['evidence_id'] for v in values],{'field':field,'effective_value':effective,'recorded_values':values,'correction_is_not_independent_verification':True}))
  if values:comparisons.append({'topic':'field:'+field,'label':field,'values':values,'status':'DIFFERENT_REPORTED_VALUES' if len({norm(v['value']) for v in values})>1 else 'SAME_REPORTED_VALUE'})
 policy_missing=any(isinstance(f,dict) and f.get('code')=='POLICY_NOT_FOUND' for f in result.get('findings',[]))
 for f in result.get('findings',[]):
  if not isinstance(f,dict) or f.get('code') in ('REPAIR_ITEM_REQUIRES_VERIFICATION','INVOICE_TOTAL_MISMATCH'):continue
  if policy_missing and f.get('code') in ('UNVERIFIED_POLICY_SOURCE','POLICY_STATUS_REQUIRES_REVIEW'):continue
  # Existing deterministic checks have provenance of rule/policy inputs, not fabricated document citations.
  if f.get('source')=='RULE':findings.append(finding(f.get('code','RULE'),f.get('severity','MEDIUM'),f.get('message',''),[],{'basis':'RECORDED_RULE','status':f.get('verification_status')}))
 present={d['role'] for d in documents};tasks=[]
 for key,label in ROLES.items():
  if key not in present:tasks.append({'key':'missing:'+key,'kind':'MISSING_DOCUMENT','title':'استكمال '+label,'reason':'لم يُصنّف مستند بهذا الدور؛ راجع التصنيف أو أرفق المستند.','role':key,'evidence_ids':[]})
 for cov in coverage:
  if not cov['complete']:tasks.append({'key':'reading:'+cov['document_id'],'kind':'READING_REVIEW','title':'مراجعة قراءة '+cov['name'],'reason':'تغطية القراءة غير مكتملة أو غير مؤكدة؛ قارن الأصل أو أعد رفع نسخة أوضح.','document_id':cov['document_id'],'evidence_ids':[]})
 for part,(label,_) in PARTS.items():
  invoiced=[r for r in comparisons if r.get('topic')==part and r.get('role')=='invoice' and r.get('evidence_ids')]
  checked=[r for r in comparisons if r.get('topic')==part and r.get('role') in ('incident','inspection')]
  if invoiced and checked:
   negatives=[r for r in checked if r['status']=='NEGATIVE_TEXT']
   absent=[r for r in checked if r['status']=='NOT_MENTIONED_IN_READ_TEXT']
   if negatives or absent:
    ev=[e for r in invoiced+(negatives or []) for e in r['evidence_ids']]
    text=('ورد نفي لفظي بجانب '+label+' في تقرير، مع ذكره في الفاتورة؛ يجب تفسير السياق.' if negatives else 'ذُكر '+label+' في الفاتورة ولم يُذكر في النص المقروء الكامل للتقارير المتاحة؛ يلزم توضيح العلاقة.')
    f=finding('DAMAGE_CONTEXT_REVIEW','MEDIUM',text,ev,{'topic':part,'scope_documents':[r['document_id'] for r in checked],'absence_is_not_denial':True});findings.append(f)
    tasks.append({'key':'explain:'+part,'kind':'CLARIFICATION','title':'توضيح بند '+label,'reason':text,'evidence_ids':ev})
 policy_findings=[f for f in findings if f['code'].startswith(('POLICY_','UNVERIFIED_POLICY'))]
 if policy_findings:tasks.append({'key':'policy:verification','kind':'CLARIFICATION','title':'استكمال التحقق من سجل الوثيقة','reason':'راجع مصدر السجل وحالته والمطابقات المطلوبة. غياب السجل لا يعني رفض المطالبة.','evidence_ids':[]})
 for f in findings:
  if f['severity']=='HIGH' and f not in policy_findings:tasks.append({'key':'finding:'+f['id'],'kind':'CLARIFICATION','title':'تدقيق ملاحظة ذات أولوية مرتفعة','reason':f['text'],'evidence_ids':f['evidence_ids']})
 total=sum(c['expected_pages'] or c['observed_pages'] for c in coverage);read=sum(p['status']=='READ' for c in coverage for p in c['pages'])
 return {'schema_version':VERSION,'case_id':case_id,'claim_version':version,'sources':sources,'documents':documents,'coverage':{'documents':coverage,'total_pages':total,'unknown_documents':sum(c['expected_pages'] is None for c in coverage),'read_pages':read,'complete':bool(coverage) and all(c['complete'] for c in coverage)},'comparisons':comparisons,'invoice_rows':invoices,'findings':findings,'tasks':tasks,'fields':result.get('extracted',{}),'field_quality':result.get('field_quality',{}),'policy_verification':result.get('policy_verification',{}),'model_assertions':[],'withheld':[],'decision_notice':'تقرير أولي للمراجع؛ لا يثبت أصالة المستند أو التغطية أو استحقاق الدفع.'}

def finding(code,severity,text,ids,checks):return {'id':uid(code,text,ids),'code':code,'severity':severity,'text':text,'evidence_ids':list(dict.fromkeys(ids)),'origin':'DETERMINISTIC_CHECK','checks':checks}

def invoice_rows(doc,page,addsource,sources,findings):
 rows=[];text=document_reader.normalize(page.get('text','')) # normalization is only for amounts, not citation positions
 lines=page.get('text','').splitlines();unparsed=[]
 for index,line in enumerate(lines):
  hits=list(MONEY.finditer(document_reader.normalize(line)))
  if not hits:continue
  previous=lines[index-1].strip() if index else ''
  label=MONEY.sub('',document_reader.normalize(line)).strip(' :|-') or previous
  if not label or re.search(r'invoice\s*(?:number|id)|\bINV-',label,re.I):continue
  quote=line if label in document_reader.normalize(line) else previous+'\n'+line
  ev=addsource(doc,page,quote)
  if not ev:ev=addsource(doc,page,line)
  if len(hits)==2:
   # Explicit pipe-separated quantity/unit/line-total layout only.
   columns=[c.strip() for c in document_reader.normalize(line).split('|')]
   if len(columns)==4 and re.fullmatch(r'\d+(?:\.\d{1,3})?',columns[1]) and MONEY.fullmatch(columns[2]) and MONEY.fullmatch(columns[3]) and hits[0][1].upper()==hits[1][1].upper():
    quantity=Decimal(columns[1]);unit=Decimal(hits[0][2].replace(',',''));total=Decimal(hits[1][2].replace(',',''))
    rows.append({'label':columns[0],'amount':str(total),'currency':hits[1][1].upper(),'kind':'ITEM','evidence_id':ev,'document_id':doc['document_id'],'page':page['page'],'quantity':str(quantity),'unit_price':str(unit)})
    if abs(quantity*unit-total)>Decimal('.001'):findings.append(finding('LINE_MULTIPLICATION_DIFFERENCE','HIGH','الكمية مضروبة بسعر الوحدة تختلف عن إجمالي السطر المطبوع.',[ev],{'computed':str(quantity*unit),'recorded':str(total),'currency':hits[1][1].upper()}))
    continue
   unparsed.append(ev);continue
  if len(hits)!=1:unparsed.append(ev);continue
  hit=hits[0];kind='TOTAL' if re.fullmatch(r'total|grand total|الإجمالي|المجموع',label,re.I) else 'SUBTOTAL' if re.search(r'subtotal|المجموع الفرعي',label,re.I) else 'TAX' if re.search(r'\btax\b|ضريبة',label,re.I) else 'DISCOUNT' if re.search(r'discount|خصم',label,re.I) else 'ITEM'
  # Only explicit line totals are interpreted; quantity and unit price are not guessed.
  rows.append({'label':label,'amount':str(Decimal(hit[2].replace(',',''))),'currency':hit[1].upper(),'kind':kind,'evidence_id':ev,'document_id':doc['document_id'],'page':page['page'],'quantity':None,'unit_price':None})
 totals=[r for r in rows if r['kind']=='TOTAL'];parts=[r for r in rows if r['kind']=='ITEM'];currencies={r['currency'] for r in rows}
 eligible=len(totals)==1 and len(parts)>=2 and len(currencies)==1 and not unparsed and document_reader.usable_page(page) and not page.get('read_flags') and not doc.get('uncertainties') and not any(r['kind']=='SUBTOTAL' for r in rows)
 if eligible:
  summed=sum(Decimal(r['amount'])*(-1 if r['kind']=='DISCOUNT' else 1) for r in rows if r['kind']!='TOTAL');actual=Decimal(totals[0]['amount'])
  ids=[r['evidence_id'] for r in rows]
  findings.append(finding('INVOICE_ARITHMETIC_MATCH' if abs(summed-actual)<=Decimal('.001') else 'INVOICE_ARITHMETIC_DIFFERENCE','LOW' if abs(summed-actual)<=Decimal('.001') else 'HIGH','مجموع الأسطر المقروءة يطابق الإجمالي المطبوع.' if abs(summed-actual)<=Decimal('.001') else 'مجموع الأسطر المقروءة يختلف عن الإجمالي المطبوع؛ راجع معنى البنود واكتمال الجدول.',ids,{'scope':'READ_LINE_AMOUNTS_ONLY','computed':str(summed),'recorded':str(actual),'currency':totals[0]['currency'],'not_market_price_verification':True}))
 elif rows:findings.append(finding('INVOICE_ARITHMETIC_INCOMPLETE','MEDIUM','تعذر حسم الحساب آليًا لهذا الجدول؛ تظهر المبالغ المقروءة للمراجعة.',[r['evidence_id'] for r in rows],{'scope':'UNSUPPORTED_OR_INCOMPLETE_TABLE'}))
 return rows

def analyst_packet(report):
 sources=[s for s in report['sources'].values() if s['readable']]
 sources.sort(key=lambda s:-(bool(re.search(r'discrepancy|uncertain|not |لم |لا |damage|ضرر|JOD|USD',s['quote'],re.I))))
 selected=sources[:12]
 return {'case_id':report['case_id'],'claim_version':report['claim_version'],'scope':'SELECTED_PASSAGES_NOT_FULL_DOCUMENT_REVIEW','coverage':{'complete':report['coverage']['complete'],'total_pages':report['coverage']['total_pages'],'read_pages':report['coverage']['read_pages']},'sources':[{'evidence_id':s['evidence_id'],'document_id':s['document_id'],'page':s['page'],'quote':s['quote'][:1000]} for s in selected]}

def parse(raw):
 if isinstance(raw,str):
  try:return json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip()))
  except ValueError:return {}
 return raw if isinstance(raw,dict) else {}

def proposals(report,raw,allowed_ids):
 data=parse(raw);accepted=[];withheld=[]
 for item in data.get('observations',[])[:8] if isinstance(data.get('observations'),list) else []:
  if not isinstance(item,dict):continue
  text=item.get('text');ids=item.get('evidence_ids');kind=item.get('kind')
  good=isinstance(text,str) and 3<=len(text)<=240 and len(re.findall(r'[.!?؟](?:\s|$)',text))<=1 and isinstance(ids,list) and 1<=len(ids)<=4 and all(isinstance(e,str) and e in allowed_ids and e in report['sources'] and report['sources'][e]['readable'] for e in ids) and kind in ('CLARIFICATION','REPORTED_DIFFERENCE','DOCUMENT_STATEMENT')
  if good and kind=='REPORTED_DIFFERENCE':good=len({report['sources'][e]['document_id'] for e in ids})>=2
  # Absence and insurance decisions are never delegated to the language model.
  if good and re.search(r'approved|rejected|fraud|coverage|eligible|payment|مقبول|مرفوض|احتيال|تغطية|مستحق|يستحق|يجب دفع|لم يرد|لم يذكر|لم يُذكر|لا يوجد|not mentioned|not found|missing|absent',text,re.I):good=False
  if good:
   evidence=' '.join(report['sources'][e]['quote'] for e in ids)
   nums=re.findall(r'\d+(?:[.,]\d+)*',norm(text));evnums=re.findall(r'\d+(?:[.,]\d+)*',norm(evidence))
   if any(n not in evnums for n in nums):good=False
  if not good:withheld.append({'text':str(text)[:500],'reason':'INVALID_SCOPE_SOURCE_OR_ASSERTION_BOUNDARY'});continue
  accepted.append({'assertion_id':uid(text,ids),'text':text,'kind':kind,'evidence_ids':ids})
 return accepted,withheld

def verifier_packet(report,assertions):
 return {'instruction':'Assess each atomic claim from original evidence and context. Do not accept analyst reasoning as evidence. SUPPORTED means the cited context actually entails the entire claim. Negation, uncertainty and scope matter. Otherwise CONTRADICTED or INSUFFICIENT.', 'assertions':[{'assertion_id':a['assertion_id'],'text':a['text'],'sources':[{'evidence_id':e,'quote':report['sources'][e]['quote'],'context':report['sources'][e]['context']} for e in a['evidence_ids']]} for a in assertions]}

def gate(report,assertions,raw):
 data=parse(raw);reviews=data.get('reviews',[]);byid={}
 for r in reviews if isinstance(reviews,list) else []:
  if isinstance(r,dict) and isinstance(r.get('assertion_id'),str):byid.setdefault(r['assertion_id'],[]).append(r)
 for a in assertions:
  rs=byid.get(a['assertion_id'],[]);r=rs[0] if len(rs)==1 else {}
  supported=r.get('status')=='SUPPORTED' and isinstance(r.get('reason'),str) and r['reason'].strip() and isinstance(r.get('evidence_ids'),list) and all(isinstance(e,str) for e in r['evidence_ids']) and set(r['evidence_ids'])==set(a['evidence_ids'])
  extractive=any(norm(a['text']) in norm(report['sources'][e]['quote']) for e in a['evidence_ids'])
  rubberstamp=norm(r.get('reason',''))==norm(a['text'])
  # Live QA found correlated semantic errors in the two local calls. Until a held-out
  # domain evaluation supports free paraphrase, only extractive statements may publish.
  if supported and extractive and not rubberstamp:
   report['model_assertions'].append({**a,'origin':'MODEL_REVIEWED_EXTRACT','review_reason':r['reason'][:600],'notice':'اقتباس رشّحه النموذج وطابق النص؛ لا يثبت صحة المستند.'})
  else:report['withheld'].append({**a,'reason':'HUMAN_CONFIRMATION_REQUIRED_FOR_PARAPHRASE' if supported and not extractive else 'COPIED_ASSERTION_IS_NOT_AUDIT' if rubberstamp else r.get('reason') or 'NO_UNAMBIGUOUS_SUPPORT_REVIEW','audit_reason':r.get('reason'),'status':'REQUIRES_HUMAN_CONFIRMATION' if supported and not extractive else r.get('status','INSUFFICIENT')})
 return report
