const reliableDetail=renderDetail;
renderDetail=function(c){
 let html=reliableDetail(c);if(c.status==='failed')html+='<p id="processing-failure" class="notice" role="status">جارٍ تحميل سبب التعذر…</p>';if(!c.result||c.status==='preparing')return html;
 const r=reviewResult(c),v=r.policy_verification||{},q=r.field_quality||{};
 const labels={MATCH:'متطابق مع السجل',MISMATCH:'مختلف عن السجل',NOT_VERIFIED:'لم يُتحقق',UNVERIFIED:'لم يُتحقق',OBSERVED:'مرصود من المستند؛ غير موثّق مستقلًا',CORRECTED:'تصحيح موظف',CONFLICT:'قيم متعارضة',MISSING:'ناقص'};
 html+=`<details class="review-history"><summary>ما الذي تحقق منه النظام؟</summary><p class="muted">نجاح التنفيذ لا يعني صحة المستند أو اعتماد التغطية.</p>${[['مطابقة المركبة',v.vehicle_check],['مطابقة نوع التأمين',v.type_check],['التغطية',v.coverage_status]].map(([label,status])=>`<p>${esc(label)}: <strong>${esc(labels[status]||'لم يُتحقق')}</strong></p>`).join('')}${Object.entries(q).map(([key,value])=>`<p>${esc(fieldLabels[key]||key)}: ${esc(labels[value.status]||value.status)}</p>`).join('')}</details>`;
 if(c.review_sync)html+=`<p role="status" class="notice">${c.review_sync==='synced'?'تمت مزامنة إجراء المراجعة مع مهام قاعدة البيانات.':'حُفظ إجراء المراجعة محليًا؛ مزامنة المهام في قاعدة البيانات قيد المحاولة.'}</p>`;
 html+=`<section class="review-resolution"><h2>مساعد المراجع</h2><p class="muted">يساعدك في البحث داخل أدلة هذه المعاملة فقط. إجابته مسودة تحتاج تدقيقًا ولا تغيّر البيانات أو تتخذ قرارًا.</p><form onsubmit="askReviewAssistant(event)"><label class="field">سؤالك عن الأدلة<textarea name="question" rows="2" minlength="3" maxlength="1000" required placeholder="مثال: أين ورد إصلاح الغطاء وما الذي يحتاج تحققًا؟"></textarea></label><button class="ghost" type="submit">ابحث في الأدلة</button></form><div id="assistant-answer" aria-live="polite"></div></section>`;
 return html;
};
async function askReviewAssistant(event){
 event.preventDefault();const form=event.currentTarget,button=form.querySelector('button'),id=currentId;
 const target=$('assistant-answer');button.disabled=true;target.textContent='جارٍ البحث في أدلة المعاملة…';
 try{
  const answer=await api('/cases/'+encodeURIComponent(id)+'/assistant','POST',{question:new FormData(form).get('question')});
  if(currentId!==id||!$('assistant-answer'))return;
  $('assistant-answer').innerHTML=`<p class="review-summary">${esc(answer.answer)}</p><p class="muted">${esc(answer.notice||'مسودة تحتاج مراجعة.')}</p>${(answer.citations||[]).map(ref=>`<section class="source-match"><button class="ghost" data-doc="${esc(ref.document_id)}" data-page="${esc(ref.page)}" onclick="openAssistantSource(this.dataset.doc,this.dataset.page)">فتح المصدر · الصفحة ${esc(ref.page)}</button><blockquote dir="auto">${esc(ref.quote)}</blockquote></section>`).join('')}`;
 }catch(e){if(currentId===id&&$('assistant-answer'))$('assistant-answer').textContent=e.message}
 finally{button.disabled=false}
}
function openAssistantSource(id,page){
 const s=evidenceReview;if(!s)return;const i=s.documents.findIndex(d=>d.id===id);if(i<0)return;
 const doc=s.evidence.find(d=>d.document_id===id),p=(doc?.pages||[]).findIndex(p=>String(p.page)===String(page));
 selectEvidence(i,'text',Math.max(0,p));$('evidence-panel').scrollIntoView({behavior:'smooth',block:'start'});
}
const reviewedDecision=decide;
decide=async function(id,decision){
 const note=$('note-'+id)?.value.trim();if(!note){toast('اكتب سبب المراجعة أولًا');return}
 const origin=typeof reviewUI!=='undefined'?reviewUI.context():null;const c=evidenceReview?.case;if(!c||c.id!==id){toast('أعد فتح المعاملة قبل تسجيل المراجعة');return}
 try{await api('/cases/'+encodeURIComponent(id)+'/review','POST',{decision,note,version:c.current_version??reviewResult(c).claim_version});await refresh();if(origin?reviewUI.current(origin):currentId===id&&page==='results')render();toast('حُفظت المراجعة، وتتم مزامنتها مع قاعدة البيانات')}catch(e){toast(e.message)}
};
const reliableLoadDetail=loadDetail;let reviewSyncTimer=null;
loadDetail=async function(id){
 await reliableLoadDetail(id);if(currentId!==id||page!=='results')return;
 if($('processing-failure')){
  try{const jobs=await api('/cases/'+encodeURIComponent(id)+'/jobs');const error=jobs[jobs.length-1]?.error||'';if($('processing-failure'))$('processing-failure').textContent=error.includes('Stop Conflicting')?'يوجد تعارض مع مهمة مراجعة سابقة. حُفظ السجل القديم؛ راجع البيانات وأعد التحليل بإصدار جديد.':error.startsWith('N8N_NODE_FAILURE')?'توقفت إحدى خطوات المعالجة. راجع البيانات أو حالة الخدمات ثم أعد المحاولة.':error==='CallbackTimeout'?'لم تصل النتيجة في الوقت المتوقع. تحقق من الربط قبل إعادة المحاولة.':'تعذرت المعالجة؛ احتفظنا بالمستندات والإصدارات السابقة.'}catch{}
 }
 clearTimeout(reviewSyncTimer);if(evidenceReview?.case.review_sync&&evidenceReview.case.review_sync!=='synced')reviewSyncTimer=setTimeout(()=>{if(connected&&page==='results'&&currentId===id)loadDetail(id)},5000);
};
