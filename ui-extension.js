// Functional additions using the existing interface components and styling.
const baseRenderDetail=renderDetail;
renderDetail=function(c){
 let html=baseRenderDetail(c);
 if(!connected)return html;
 if(c.status==='failed')html+=`<div class="notice">تعذرت المعالجة. يمكنك تصحيح البيانات بإصدار جديد أو إعادة المحاولة عند إصلاح سبب التعذر.</div><button class="primary" onclick="retryCase('${esc(c.id)}')">إعادة المحاولة</button>`;
 if(!['review','failed'].includes(c.status))return html;
 let r={};try{r=typeof c.result==='string'?JSON.parse(c.result):c.result||{}}catch{}
 const fields=r.extracted||c.failed_fields||{};
 const labels={policy_number:'رقم الوثيقة',accident_date:'تاريخ الحادث',vehicle_plate:'رقم المركبة',incident_description:'وصف الحادث'};
 html+=`<details style="margin-top:24px"><summary>تصحيح البيانات وإعادة التحليل</summary><p class="muted">يُحفظ التصحيح بإصدار جديد وسبب مكتوب، وتبقى الأدلة والنتائج السابقة محفوظة.</p><form id="correction-form" onsubmit="reanalyzeCase(event,'${esc(c.id)}')"><div class="formrow">${Object.entries(labels).map(([key,label])=>`<label class="field ${key==='incident_description'?'wide':''}">${label}<input name="${key}" value="${esc(fields[key]||'')}" ${key==='accident_date'?'type="date"':''} maxlength="${key==='incident_description'?10000:150}"></label>`).join('')}<label class="field wide">سبب التحديث<textarea name="reason" required maxlength="2000" rows="3"></textarea></label></div><button class="primary" type="submit">حفظ التعديل وتحديث التقرير</button></form></details>`;
 return html;
};
loadDetail=async function(id){
 try{
  const c=await api('/cases/'+encodeURIComponent(id));
  if(currentId!==id||page!=='results')return;
  if($('detail'))$('detail').innerHTML=renderDetail(c);
  let evidence=[];try{evidence=await api('/cases/'+encodeURIComponent(id)+'/evidence')}catch{}
  if(currentId!==id||page!=='results')return;
  if($('docs'))$('docs').innerHTML=(c.documents||[]).map(d=>{
   const e=evidence.find(x=>x.document_id===d.id);
   return `<section style="margin-bottom:18px"><strong>${esc(d.original_name)}</strong><p><button class="ghost" onclick="downloadEvidence('${esc(d.id)}','${esc(d.id)}')">تحميل المستند الأصلي</button></p><small>${esc(e?.method||'لم يعالج بعد')} · ${esc(e?.status||'pending')}</small>${(e?.uncertainties||[]).map(u=>`<div class="notice">${esc(u)}</div>`).join('')}${(e?.pages||[]).map(p=>`<details><summary>نص المصدر · الصفحة ${esc(p.page)}</summary><pre dir="auto" style="white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px">${esc(p.text)}</pre></details>`).join('')}</section>`;
  }).join('')||'<p>لا توجد مستندات.</p>';
  const history=await api('/cases/'+encodeURIComponent(id)+'/history');
  if(currentId===id&&page==='results'&&$('docs'))$('docs').insertAdjacentHTML('beforeend',`<details style="margin-top:20px"><summary>سجل إصدارات التحليل (${history.length})</summary>${history.map(h=>`<details><summary>الإصدار ${esc(h.version)} · ${esc(h.created_at)}</summary><pre dir="auto" style="white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px">${esc(JSON.stringify(JSON.parse(h.result),null,2))}</pre></details>`).join('')}</details>`);
 }catch(e){toast(e.message)}
};
async function downloadEvidence(id,name){
 try{
  const r=await fetch('/api/documents/'+encodeURIComponent(id),{headers:{Authorization:'Bearer '+token}});
  if(!r.ok)throw Error('تعذر تحميل المستند');
  const url=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
 }catch(e){toast(e.message)}
}
async function reanalyzeCase(event,id){
 event.preventDefault();const form=event.currentTarget,button=form.querySelector('button[type="submit"]');
 if(!evidenceReview||evidenceReview.case_id!==id||v2State?.is_current===false){toast('افتح الإصدار الحالي قبل التصحيح.');return}
 const data=new FormData(form),original=reviewResult(evidenceReview.case).extracted||evidenceReview.case.failed_fields||{},fields=Object.fromEntries([...data.entries()].filter(([key,value])=>key!=='reason'&&String(value)!==String(original[key]||'')));
 button.disabled=true;
 try{
  await api('/cases/'+encodeURIComponent(id)+'/reanalyze','POST',{fields,note:data.get('reason'),version:evidenceReview.case.current_version},{'X-Role':'supervisor'});
  currentId=id;await refresh();render();startPolling();toast('حُفظ التصحيح وبدأ إصدار تحليل جديد');
 }catch(e){button.disabled=false;toast(e.message)}
}
async function retryCase(id){
 try{await api('/cases/'+encodeURIComponent(id)+'/retry','POST',{});currentId=id;await refresh();render();startPolling();toast('بدأت إعادة المحاولة')}catch(e){toast(e.message)}
}
const baseBadge=badge;
badge=function(s){if(s==='approved')return '<span class="pill done">مراجعة مسجلة</span>';if(s==='rejected')return '<span class="pill review">مراجعة غير معتمدة</span>';return s==='failed'?'<span class="pill review">تعذرت المعالجة</span>':s==='preparing'?'<span class="pill processing">استخراج المستندات</span>':baseBadge(s)};
const readerBaseStatus=analysisStatus;
analysisStatus=function(){const c=cases.find(x=>x.id===currentId)||cases.find(x=>x.status==='preparing');if(c?.status!=='preparing')return readerBaseStatus();return `<div class="notice" role="status"><strong>${esc(c.id)} · جارٍ قراءة المستندات</strong><p>نستخرج النص ونقرأ الصور عند الحاجة، ثم نجهّز البيانات للتحقق في n8n. قد تستغرق الصفحات الممسوحة وقتًا أطول.</p><p>يمكنك متابعة المعاملات؛ ستتحدث الحالة تلقائيًا.</p></div>`};
const baseConnect=connect;
connect=async function(){await baseConnect();if(connected)startPolling()};
startPolling=function(){
 clearInterval(poller);
 poller=setInterval(async()=>{
  if(!connected){clearInterval(poller);return}
  try{
   const previous=new Map(cases.map(c=>[c.id,c.status]));await refresh();
   const changed=cases.some(c=>previous.has(c.id)&&previous.get(c.id)!==c.status);
   if(changed){if(page!=='results'||!$('correction-form'))render()}
  }catch{}
 },3000);
};

// Preserve intake text across file-picker rerenders; retries reuse the saved draft.
let intakeDraft={client:'',notes:''},pendingIntake=new Map();
const intakeHome=home;
home=function(){return intakeHome().replace('id="client"','id="client" value="'+esc(intakeDraft.client)+'"').replace('placeholder="اختياري"></textarea>','placeholder="اختياري">'+esc(intakeDraft.notes)+'</textarea>')};
document.addEventListener('input',event=>{if(page==='home'&&['client','notes'].includes(event.target.id))intakeDraft[event.target.id]=event.target.value});

// Display labels only; stored case and audit values stay unchanged.
const employeeCaseTable=table;
table=function(items){return employeeCaseTable(items.map(item=>({...item,kind:item.kind==='motor'?'مطالبة مركبة':item.kind})))};
const employeeActions={created:'إنشاء المعاملة',document_uploaded:'إرفاق مستند',queued:'إرسال المعاملة للمعالجة',result_received:'وصول نتيجة التحليل',corrected:'تحديث بيانات المعاملة',approved:'تسجيل اعتماد المراجعة',rejected:'تسجيل عدم اعتماد المراجعة',review_synced:'مزامنة المراجعة',v2_report_published:'تجهيز التقرير',followup_changed:'تحديث المتابعة',document_role_changed:'تعديل نوع المستند',supplement_uploaded:'إضافة مستند استكمال',assistant_response:'البحث في المستندات',assistant_failed:'تعذر البحث',report_retry:'إعادة تجهيز التقرير'};
tableLogs=function(){return `<div class="table-wrap"><table><thead><tr><th>التاريخ</th><th>الإجراء</th><th>المستخدم</th></tr></thead><tbody>${logs.map(x=>`<tr><td>${esc(new Date(x.created_at).toLocaleString('ar-JO'))}</td><td>${esc(employeeActions[x.action]||'إجراء على المعاملة')}</td><td>${esc(x.actor)}</td></tr>`).join('')}</tbody></table></div>`};
