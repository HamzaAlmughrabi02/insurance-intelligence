let reviewQueue=[],reviewQuery='',reviewCategory='all',reviewQueueRequest=0,reviewQueueTimer=null,reviewContext=false;
function queueFindings(item){const priority={HIGH:0,MEDIUM:1,LOW:2};const rank={repair:0,hood:0,'policy-conflict':0,date:0,'policy-missing':1,'policy-source':2,'policy-status':2,evidence:3};return collectFindings({flags:item.reasons||[]}).sort((a,b)=>(priority[a.severity]??2)-(priority[b.severity]??2)||(rank[a.key]??2)-(rank[b.key]??2))}
function queueDate(value){const d=new Date(value);return Number.isNaN(d.getTime())?'تاريخ غير متاح':d.toLocaleDateString('ar-JO',{year:'numeric',month:'short',day:'numeric'})}
reviewPage=function(){return `<section class="card"><div class="queue-heading"><div><h2>قائمة المراجعة</h2><p class="queue-help">افتح المعاملة لمعرفة سبب الإحالة ومقارنة المعلومات مع المستندات، ثم سجّل نتيجة مراجعتك.</p></div><span class="chip" id="queue-count">جارٍ التحميل…</span></div><div class="queue-tools"><label>البحث عن معاملة أو عميل<input id="queue-search" type="search" value="${esc(reviewQuery)}" placeholder="مرجع العميل، رقم المعاملة أو الوثيقة" oninput="reviewQuery=this.value;renderQueueRows()"></label><label>سبب المراجعة<select id="queue-filter" onchange="reviewCategory=this.value;renderQueueRows()"><option value="all" ${reviewCategory==='all'?'selected':''}>جميع الأسباب</option><option value="documents" ${reviewCategory==='documents'?'selected':''}>المستندات والأدلة</option><option value="policy" ${reviewCategory==='policy'?'selected':''}>الوثيقة والتحقق</option><option value="data" ${reviewCategory==='data'?'selected':''}>بيانات تحتاج استكمالًا</option></select></label><button type="button" class="ghost" onclick="loadReviewQueue()">تحديث القائمة</button></div><div id="queue-results" aria-live="polite"><p class="queue-empty">جارٍ تحميل المعاملات وأسباب مراجعتها…</p></div><div class="queue-footer"><span>مرجع العميل هو المرجع الذي أدخل عند إنشاء المعاملة؛ ليس إثبات هوية.</span><span>تتحدث القائمة تلقائيًا أثناء فتحها.</span></div></section>`};
function queueMatches(item){
 const reasons=queueFindings(item),text=[item.id,item.client,item.policy_number,...reasons.map(f=>f.title+' '+f.detail)].join(' ').toLocaleLowerCase();
 if(reviewQuery&&!text.includes(reviewQuery.trim().toLocaleLowerCase()))return false;
 if(reviewCategory==='policy')return reasons.some(f=>f.key.startsWith('policy')||f.key==='date');
 if(reviewCategory==='documents')return reasons.some(f=>['hood','evidence'].includes(f.key)||/DOCUMENT|READABLE|OCR/.test(f.key));
 if(reviewCategory==='data')return reasons.some(f=>f.field&&!f.key.startsWith('policy'));
 return true;
}
function renderQueueRows(){
 if(page!=='review'||!$('queue-results'))return;
 const visible=reviewQueue.filter(queueMatches);$('queue-count').textContent=reviewQueue.length+' معاملة بانتظار المراجعة';
 $('queue-results').innerHTML=visible.length?visible.map(item=>{
  const reasons=queueFindings(item),first=reasons[0];
  return `<article class="queue-row"><div><div class="queue-ref">مرجع العميل</div><div class="queue-client">${esc(item.client||'مرجع العميل غير مسجل')}</div><div class="queue-ref"><bdi>${esc(item.id)}</bdi> · ${esc(item.kind)}</div><div class="queue-ref">${item.policy_number?'الوثيقة: <bdi>'+esc(item.policy_number)+'</bdi>':'رقم الوثيقة يحتاج استكمالًا'} · ${Number(item.document_count)||0} مستندات</div><div class="queue-ref">${esc(queueDate(item.created_at))}${item.claim_version?' · إصدار '+esc(item.claim_version):''}</div></div><div><p class="queue-reason"><strong>${esc(first?.title||'مراجعة بشرية مطلوبة للتحليل الأولي')}</strong></p><p class="queue-reason">${esc(first?.detail||'راجع بيانات المطالبة والأدلة قبل تسجيل أي إجراء.')}</p>${reasons.length>1?`<p class="queue-more">و${reasons.length-1} ملاحظات أخرى داخل المعاملة</p>`:''}</div><button type="button" class="primary queue-action" onclick="openReviewCase('${esc(item.id)}')">فتح المراجعة والأدلة</button></article>`
 }).join(''):`<div class="queue-empty">${reviewQueue.length?'لا توجد معاملات تطابق البحث أو السبب المحدد.':'لا توجد معاملات بانتظار المراجعة حاليًا.'}</div>`;
}
async function loadReviewQueue(){
 const request=++reviewQueueRequest;
 try{
  const items=await api('/review-queue');if(request!==reviewQueueRequest||page!=='review')return;
  reviewQueue=items;renderQueueRows();
 }catch(e){if(page==='review'&&$('queue-results'))$('queue-results').innerHTML=`<div class="queue-error">تعذر تحميل قائمة المراجعة. ${esc(e.message)}<br><button class="ghost" onclick="loadReviewQueue()">إعادة المحاولة</button></div>`}
}
const reviewBaseGo=go;
go=function(target){
 reviewNavigation++;
 if(target==='review'){reviewContext=false;currentId='';history.pushState(null,'','#review')}
 else if(target!=='results'){reviewContext=false;if(location.hash.startsWith('#review'))history.replaceState(null,'',location.pathname+location.search)}
 reviewBaseGo(target);
};
let reviewNavigation=0;
async function showReviewCase(id,push){
 const navigation=++reviewNavigation,origin=typeof reviewUI!=='undefined'?reviewUI.navigate():null;
 try{
  const item=await api('/cases/'+encodeURIComponent(id));
  if(navigation!==reviewNavigation||(origin!==null&&!reviewUI.latest(origin)))return;
  const index=cases.findIndex(c=>c.id===id);if(index<0)cases.push(item);else cases[index]={...cases[index],...item};
  currentId=id;reviewContext=true;if(push)history.pushState(null,'','#review/'+encodeURIComponent(id));reviewBaseGo('results');
 }catch(e){if(navigation===reviewNavigation&&(origin===null||reviewUI.latest(origin)))toast(e.message)}
}
function openReviewCase(id){return showReviewCase(id,true)}
function returnToReview(){reviewNavigation++;if(typeof reviewUI!=='undefined')reviewUI.navigate();reviewContext=false;currentId='';history.pushState(null,'','#review');reviewBaseGo('review')}
const reviewBaseResultPage=resultPage;
resultPage=function(){const c=cases.find(c=>c.id===currentId);return (reviewContext?'<button type="button" class="review-back" onclick="returnToReview()">العودة إلى قائمة المراجعة</button>':c?.status==='review'?`<button type="button" class="review-back" onclick="openReviewCase('${esc(c.id)}')">فتح هذه المعاملة في مركز المراجعة</button>`:'')+reviewBaseResultPage()};
const reviewBaseLoadDetail=loadDetail;
loadDetail=async function(id){
 await reviewBaseLoadDetail(id);if(!reviewContext||page!=='results'||currentId!==id||!evidenceReview||evidenceReview.case_id!==id||!$('detail'))return;
 const c=evidenceReview.case;if(c.status!=='review')return;
 if(typeof accountSession!=='undefined'&&accountSession?.user.role!=='admin')return;
 $('review-resolution')?.remove();
 $('detail').insertAdjacentHTML('beforeend',`<section class="review-resolution" id="review-resolution"><h2>تسجيل نتيجة المراجعة</h2><p>راجع الأدلة، ثم سجّل نتيجة المراجعة وسببها. التسجيل هنا لا ينفّذ قرار تغطية أو صرف.</p><label class="field">سبب الإجراء<textarea id="note-${esc(id)}" rows="3" maxlength="2000" placeholder="ما الذي راجعته؟ وما سبب الإجراء؟" required></textarea></label><div class="resolution-actions"><button class="primary" onclick="decide('${esc(id)}','approve')">تسجيل اعتماد المراجعة</button><button class="ghost" onclick="decide('${esc(id)}','reject')">تسجيل عدم الاعتماد</button></div></section>`);
};
const reviewBaseRender=render;
render=function(){reviewBaseRender();if(page==='review'&&connected)loadReviewQueue()};
function restoreReviewRoute(){
 if(!connected)return;reviewNavigation++;if(typeof reviewUI!=='undefined')reviewUI.navigate();const match=location.hash.match(/^#review(?:\/([^/]+))?$/);if(!match){if(reviewContext||page==='review'){reviewContext=false;reviewBaseGo('home')}return}
 if(match[1]){try{showReviewCase(decodeURIComponent(match[1]),false)}catch{reviewBaseGo('review')}}
 else{reviewContext=false;reviewBaseGo('review')}
}
window.addEventListener('popstate',restoreReviewRoute);
window.addEventListener('hashchange',restoreReviewRoute);
if(typeof enterAccount==='function'){
 const reviewEnterAccount=enterAccount;
 enterAccount=async function(session){await reviewEnterAccount(session);restoreReviewRoute();clearInterval(reviewQueueTimer);reviewQueueTimer=setInterval(()=>{if(connected&&page==='review')loadReviewQueue()},10000)};
}
