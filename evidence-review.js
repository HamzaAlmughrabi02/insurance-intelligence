// Evidence links are derived from available page text, never from invented provenance.
let evidenceReview=null,reviewLoad=0;
const previousDetailRenderer=renderDetail;
const fieldLabels={claim_number:'رقم المعاملة',policy_number:'رقم الوثيقة',claim_type:'نوع المطالبة',accident_date:'تاريخ الحادث',vehicle_plate:'رقم المركبة',incident_description:'وصف الحادث'};
function reviewResult(c){try{return typeof c.result==='string'?JSON.parse(c.result):c.result||{}}catch{return {}}}
function findingInfo(raw){
 const text=typeof raw==='string'?raw:raw?.message||raw?.description||JSON.stringify(raw);
 const diagnostic=(raw?.code||'')+' '+text;
 if(raw?.code==='REPAIR_ITEM_REQUIRES_VERIFICATION'||text==='REPAIR_ITEM_REQUIRES_VERIFICATION')return {key:'repair',title:'بند إصلاح يحتاج مقارنة بالأدلة',detail:'المبلغ والعملة يظهران في الاقتباس المرتبط أدناه. وجود البند لا يثبت علاقته بالحادث أو استحقاقه.',sources:raw?.sources||[],pattern:/hood|غطاء/i};
 if(/UNSUPPORTED_CLAIM_TYPE/.test(diagnostic))return {key:'unsupported-type',title:'نوع المعاملة يحتاج مختصًا',detail:'المسار الآلي الحالي مخصص لمطالبات المركبات. لم تُحوّل المعاملة إلى نوع آخر تلقائيًا.'};
 if(/POLICY_VEHICLE|POLICY_VEHICLE_CHECK/.test(diagnostic))return {key:text,title:'مطابقة المركبة تحتاج مراجعة',detail:text.includes('MISMATCH')?'رقم المركبة لا يتطابق مع السجل المتاح.':'لا توجد بيانات سجل كافية لتأكيد مطابقة المركبة.'};
 if(/POLICY_TYPE/.test(diagnostic))return {key:text,title:'نوع التأمين يحتاج مطابقة بالسجل',detail:'راجع نوع المطالبة ونوع التأمين المسجل؛ لا يعني هذا التنبيه رفض المطالبة.'};
 if(/HOOD_REPAIR|hood|غطاء المحرك/i.test(diagnostic))return {key:'hood',title:'إصلاح غطاء المحرك يحتاج تحققًا',detail:(/850/.test(diagnostic)?'ورد تنبيه بشأن مبلغ 850 دينارًا لإصلاح الغطاء. ':'ورد تنبيه بشأن إصلاح غطاء المحرك. ')+'قارن الفاتورة مع تقرير الحادث والفحص؛ هذا تنبيه أولي وليس قرارًا باستحقاق المبلغ.',pattern:/hood|غطاء|850/i};
 if(/DOCUMENT_EVIDENCE_REQUIRES_REVIEW/.test(diagnostic))return {key:'evidence',title:'توجد معلومات في المستندات تحتاج مراجعة',detail:'ظهرت عبارات عن معلومات غير مؤكدة أو اختلافات. راجع المواضع المرتبطة أدناه في سياقها الأصلي.',pattern:/uncertain|discrepancy|not confirmed|غير مؤكد|تعارض/i};
 if(/POLICY_NOT_FOUND|Policy record was not found/i.test(diagnostic))return {key:'policy-missing',title:'لم يُعثر على سجل الوثيقة في قاعدة البيانات',detail:'هذا متعلق ببحث النظام في سجل السياسات؛ لا يعني أن ملف الوثيقة المرفوع غير موجود. تحقق من رقمها ومصدرها المعتمد.',field:'policy_number'};
 if(/UNVERIFIED_POLICY_SOURCE|Policy source has not been verified/i.test(diagnostic))return {key:'policy-source',title:'مصدر الوثيقة لم يُوثّق بعد',detail:'الوثيقة المرفوعة لا تمنح توثيقًا تلقائيًا لمصدر السياسة. يلزم التحقق من السجل المعتمد.',field:'policy_number'};
 if(/POLICY_STATUS_REQUIRES_REVIEW|not confirmed as ACTIVE/i.test(diagnostic))return {key:'policy-status',title:'حالة الوثيقة تحتاج تأكيدًا',detail:'لم يؤكد التحقق أن حالة الوثيقة فعّالة. راجع الحالة من مصدرها المعتمد.',field:'policy_number'};
 if(/CONFLICTING_POLICY_NUMBERS/.test(diagnostic))return {key:'policy-conflict',title:'رقم الوثيقة لا يتطابق بين البيانات والمستندات',detail:'قارن رقم الوثيقة المدخل مع الأرقام الظاهرة في المصادر؛ لم تُعدّل البيانات تلقائيًا.',pattern:/POL-[A-Z0-9-]+/i,field:'policy_number'};
 if(/OCR_LOW_CONFIDENCE|OCR_PAGE_LIMIT/.test(diagnostic))return {key:text,title:'قراءة المستند تحتاج تدقيقًا',detail:'قد تكون قراءة بعض الحروف أو الأرقام غير دقيقة، أو تجاوز المستند حد المعالجة. قارن النص بالصفحة الأصلية قبل الاعتماد.'};
 if(/FIELD_CONFLICT/.test(diagnostic))return {key:text,title:'بيانات مختلفة بين المستندات',detail:'لم يُختر حقل متعارض تلقائيًا. قارن القيم في الأصول وأدخل التصحيح مع السبب.'};
 if(/CONTEXT_MODEL_UNAVAILABLE/.test(diagnostic))return {key:text,title:'اكتمل الاستخراج دون مساعدة النموذج البصري',detail:'تعذر استخدام نموذج فهم الصفحة؛ احتفظنا بالقراءة والقواعد المتاحة. راجع الحقول غير المكتملة.'};
 if(/NO_READABLE_TEXT|UNREADABLE_DOCUMENT|IMAGE_OCR_NOT_AVAILABLE|OCR_UNAVAILABLE/.test(diagnostic))return {key:text,title:'تعذر استخراج نص قابل للمراجعة',detail:'اعرض الأصل للتدقيق اليدوي. قد تكون القراءة الآلية غير متاحة أو لم تستطع قراءة الصفحة.'};
 if(/DATE_OUTSIDE_POLICY_PERIOD|outside the recorded policy period/i.test(diagnostic))return {key:'date',title:'تاريخ الحادث خارج فترة الوثيقة المسجلة',detail:'راجع تاريخ الحادث وفترة الوثيقة. هذه نتيجة مقارنة أولية وليست قرار تغطية.',field:'accident_date'};
 if(/claim_data\./.test(diagnostic)){const field=text.split('claim_data.')[1]?.split(/\s/)[0];return {key:text,title:'بيان مطلوب يحتاج استكمالًا',detail:fieldLabels[field]||text,field}}
 return {key:text,title:'ملاحظة تحتاج مراجعتك',detail:text};
}
function collectFindings(result){
 const seen=new Set();return [...(result.findings||[]),...(result.flags||[])].sort((a,b)=>Number(typeof b==='object')-Number(typeof a==='object')).map(raw=>({...findingInfo(raw),severity:raw?.severity||null})).filter(f=>{if(seen.has(f.key))return false;seen.add(f.key);return true});
}
function relatedSources(finding,evidence){
 if(finding.sources?.length)return finding.sources.filter(s=>evidence.some(d=>d.document_id===s.document_id&&(d.pages||[]).some(p=>String(p.page)===String(s.page)&&p.text.includes(s.quote)))).map(s=>({document_id:s.document_id,page:s.page,text:s.quote}));
 if(!finding.pattern)return [];
 const matches=[];
 for(const doc of evidence)for(const page of doc.pages||[]){
  const lines=String(page.text||'').split('\n');const indices=lines.map((line,index)=>finding.pattern.test(line)?index:-1).filter(i=>i>=0);
  if(indices.length){const selected=new Set();for(const i of indices)for(let j=Math.max(0,i-1);j<=Math.min(lines.length-1,i+1);j++)selected.add(j);
   matches.push({document_id:doc.document_id,page:page.page,text:[...selected].sort((a,b)=>a-b).map(i=>lines[i]).join('\n')});}
 }return matches;
}
resultPage=function(){
 const c=cases.find(c=>c.id===currentId)||cases[0];if(!c)return '<section class="card"><div class="empty">اختر معاملة لعرض نتيجتها.</div></section>';
 currentId=c.id;
 return `<div class="toolbar"><span>${esc(c.id)} · ${esc(c.client)}</span>${badge(c.status)}</div><div class="review-workspace"><section class="card"><h2>نتيجة التحليل</h2><div id="detail" aria-live="polite"><p class="muted">جارٍ تحميل النتيجة…</p></div></section><section class="card" id="evidence-panel"><h2>المستندات والأدلة</h2><p class="muted">اختر اسم الملف لعرضه، أو انتقل إلى نصه المستخرج.</p><div id="docs" aria-live="polite"><p class="muted">جارٍ تحميل المستندات…</p></div></section></div>`;
};
renderDetail=function(c){
 if(c.status==='preparing')return '<div class="notice" role="status">جارٍ قراءة المستندات وتجهيز إصدار التحليل. ستظهر النتيجة الجديدة بعد اكتمال المعالجة؛ الإصدارات السابقة محفوظة.</div>';
 const result=reviewResult(c);if(!c.result)return previousDetailRenderer(c);
 const fields=result.extracted||{};const findings=collectFindings(result);
 const local=result.analysis_type==='LOCAL_RULES_AND_DOCUMENT_EVIDENCE';
 let html=`<p class="review-summary">${esc(local?'اكتملت الفحوص الأولية. راجع البيانات المستخرجة والملاحظات المرتبطة بمصادرها قبل استكمال المراجعة.':result.summary||'وصلت نتيجة أولية تحتاج مراجعتك.')}</p><h2>البيانات المستخرجة</h2>${Object.entries(fields).map(([key,value])=>`<div class="review-kv" id="review-field-${esc(key)}"><span>${esc(fieldLabels[key]||key)}</span><strong dir="auto">${esc(key==='claim_type'&&value==='motor'?'مطالبة مركبة':typeof value==='object'?JSON.stringify(value):value)}</strong></div>`).join('')}<section class="review-findings"><h2>ملاحظات تحتاج تحققًا <small class="muted">${findings.length}</small></h2>${findings.map((f,i)=>`<button type="button" class="finding-button" onclick="showReviewFinding(${i})" aria-controls="finding-detail"><span class="finding-index">${i+1}</span><span class="finding-body"><strong>${esc(f.title)}</strong><small>${esc(f.detail)}</small></span><span class="finding-arrow" aria-hidden="true">←</span></button>`).join('')||'<p class="muted">لم ترد ملاحظات منفصلة. تبقى المراجعة البشرية مطلوبة.</p>'}<div id="finding-detail" tabindex="-1"></div></section>`;
 const origins=Object.entries(result.field_sources||{}).filter(([key,sources])=>Array.isArray(sources)&&sources.some(s=>s.quote));
 if(origins.length)html+=`<details class="review-history"><summary>مصادر البيانات المستخرجة</summary><p class="muted">اقتباسات من النص المقروء؛ قراءة OCR واقتراحات النموذج تحتاج مقارنة بالأصل.</p>${origins.map(([key,sources])=>{const source=sources.find(s=>s.quote);return `<section><button class="ghost" type="button" data-field="${esc(key)}" onclick="openExtractedFieldSource(this.dataset.field)">${esc(fieldLabels[key]||key)} · الصفحة ${esc(source.page)}</button><blockquote dir="auto">${esc(source.quote)}</blockquote><p class="muted">${source.source==='vision_grounded_quote'?'اقتراح نموذج مرتبط باقتباس':'استخراج من تسمية الحقل'} · ${source.method==='paddleocr'?'OCR':'نص المستند'}</p></section>`}).join('')}</details>`;
 const old=previousDetailRenderer(c);const correction=old.indexOf('<details style="margin-top:24px">');if(correction>=0)html+=old.slice(correction);
 return html;
};
loadDetail=async function(id){
 const request=++reviewLoad;
 try{
  const [c,evidence,history]=await Promise.all([api('/cases/'+encodeURIComponent(id)),api('/cases/'+encodeURIComponent(id)+'/evidence'),api('/cases/'+encodeURIComponent(id)+'/history')]);
  if(request!==reviewLoad||currentId!==id||page!=='results')return;
  const old=evidenceReview;const result=reviewResult(c);
  evidenceReview={case_id:id,case:c,documents:c.documents||[],evidence,history,findings:collectFindings(result),selected:old?.case_id===id?old.selected:0,mode:old?.case_id===id?old.mode:'original',page:old?.case_id===id?old.page:0};
  $('detail').innerHTML=renderDetail(c);renderEvidenceWorkspace();
 }catch(e){if(request===reviewLoad&&page==='results'){$('docs').innerHTML=`<p class="notice">${esc(e.message)}</p>`;toast(e.message)}}
};
function renderEvidenceWorkspace(){
 const s=evidenceReview;if(!s||!$('docs'))return;
 if(!s.documents.length){$('docs').innerHTML='<div class="empty">لا توجد مستندات لهذه المعاملة.</div>';return}
 s.selected=Math.max(0,Math.min(s.selected,s.documents.length-1));
 $('docs').innerHTML=`<div class="evidence-list">${s.documents.map((d,i)=>`<button type="button" class="document-link" aria-pressed="${i===s.selected}" onclick="selectEvidence(${i},'original')"><span dir="auto">${esc(d.original_name)}</span><small>${esc((d.original_name.split('.').pop()||'').toUpperCase())} ↗</small></button>`).join('')}</div><div class="evidence-toolbar"><div class="evidence-tabs" aria-label="طريقة عرض الدليل"><button type="button" aria-pressed="${s.mode==='original'}" onclick="selectEvidence(${s.selected},'original')">المستند الأصلي</button><button type="button" aria-pressed="${s.mode==='text'}" onclick="selectEvidence(${s.selected},'text')">النص المستخرج</button></div><select id="evidence-page" class="evidence-page-select" aria-label="صفحة المصدر" onchange="changeEvidencePage(this.value)"></select></div><div id="evidence-reader"></div><details class="review-history"><summary>سجل إصدارات التحليل (${s.history.length})</summary>${s.history.map(h=>`<p>الإصدار ${esc(h.version)} · ${esc(h.created_at)}</p>`).join('')}</details>`;
 renderEvidenceReader();
}
function selectEvidence(index,mode,pageIndex=0){if(!evidenceReview)return;evidenceReview.selected=index;evidenceReview.mode=mode;evidenceReview.page=pageIndex;renderEvidenceWorkspace()}
function changeEvidencePage(value){evidenceReview.page=Number(value);renderEvidenceReader()}
function renderEvidenceReader(){
 const s=evidenceReview,d=s.documents[s.selected],e=s.evidence.find(e=>e.document_id===d.id),pages=e?.pages||[];
 s.page=Math.max(0,Math.min(s.page,Math.max(0,pages.length-1)));const p=pages[s.page];const selector=$('evidence-page');
 selector.innerHTML=pages.map((p,i)=>`<option value="${i}" ${i===s.page?'selected':''}>الصفحة ${esc(p.page)}</option>`).join('');selector.disabled=!pages.length;
 const url='/api/documents/'+encodeURIComponent(d.id)+'?view=1';const ext=d.original_name.split('.').pop().toLowerCase();
 let body;
 if(s.mode==='text')body=p?.text?.trim()?`<pre class="source-text" dir="auto">${esc(p.text)}</pre>`:'<p class="reader-message">لا يتوفر نص مستخرج لهذه الصفحة. يمكنك مراجعة المستند الأصلي.</p>';
 else if(ext==='pdf')body=`<iframe title="${esc('معاينة '+d.original_name)}" src="${url}#page=${Number(p?.page)||1}"></iframe>`;
 else if(['png','jpg','jpeg'].includes(ext))body=`<img src="${url}" alt="${esc(d.original_name)}">`;
 else body='<p class="reader-message">هذا النوع لا يملك عارضًا أصليًا داخل المتصفح. افتح «النص المستخرج» لمراجعته.</p>';
 const method=p?.method||e?.method;const methodLabel=method==='paddleocr'?'قراءة صورة باستخدام OCR':method==='native_pdf'?'نص أصلي من PDF':method==='openpyxl'?'نص جدول بيانات':'نص مستخرج';
 const provenance=`<p class="muted">${esc(methodLabel)}${p?.confidence!==undefined?' · مؤشر التعرف على الحروف: '+Math.round(p.confidence*100)+'% (ليس ضمانًا لصحة الحقول)':''}${p?.method==='paddleocr'?' · قارن الأرقام بالأصل':''}</p>`;
 $('evidence-reader').innerHTML=`<div class="reader-caption"><strong dir="auto">${esc(d.original_name)}</strong>${['pdf','png','jpg','jpeg'].includes(ext)?`<a href="${url}" target="_blank" rel="noopener noreferrer">فتح الأصل في تبويب مستقل ↗</a>`:''}</div>${provenance}<div class="evidence-reader">${body}</div>`;
}
function showReviewFinding(index){
 const s=evidenceReview;if(!s)return;const finding=s.findings[index];if(!finding)return;
 const matches=relatedSources(finding,s.evidence);
 $('finding-detail').innerHTML=`<section class="finding-detail"><h3>${esc(finding.title)}</h3><p>${esc(finding.detail)}</p>${matches.length?'<p class="muted">مواضع مرتبطة بالتنبيه وفق بحث نصي؛ تحقق من السياق في الأصل.</p>':`<p>${finding.field?'هذا التنبيه متعلق ببيانات النظام والتحقق، وليس اقتباسًا من مستند.':'لا يتوفر موضع نصي محدد لهذا التنبيه. راجع الأصول دون افتراض مصدر غير مسجل.'}</p>`}${matches.map((m,i)=>{const d=s.documents.find(d=>d.id===m.document_id);return `<div class="source-match"><button type="button" class="source-action" onclick="openFindingSource(${index},${i})">${esc(d?.original_name||'مستند')} · الصفحة ${esc(m.page)} ← عرض النص</button><blockquote dir="auto">${esc(m.text)}</blockquote></div>`}).join('')}</section>`;
 $('finding-detail').focus({preventScroll:true});$('finding-detail').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'nearest'});
}
function openFindingSource(findingIndex,matchIndex){
 const s=evidenceReview,m=relatedSources(s.findings[findingIndex],s.evidence)[matchIndex];if(!m)return;
 const index=s.documents.findIndex(d=>d.id===m.document_id);if(index<0)return;
 const e=s.evidence.find(e=>e.document_id===m.document_id);const p=e.pages.findIndex(p=>String(p.page)===String(m.page));selectEvidence(index,'text',Math.max(0,p));
 $('evidence-panel').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
}
function openExtractedFieldSource(field){
 const s=evidenceReview;if(!s)return;const source=(reviewResult(s.case).field_sources?.[field]||[]).find(x=>x.quote&&x.document_id);if(!source)return;
 const index=s.documents.findIndex(d=>d.id===source.document_id);if(index<0)return;
 const e=s.evidence.find(e=>e.document_id===source.document_id);const p=(e?.pages||[]).findIndex(p=>String(p.page)===String(source.page));
 selectEvidence(index,'text',Math.max(0,p));$('evidence-panel').scrollIntoView({behavior:'smooth',block:'start'});
}
