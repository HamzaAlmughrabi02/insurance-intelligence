// Shared in-memory state. Customer data and credentials never use browser storage.
let page='cases',files=[],token='',connected=false,busy=false,currentId='',poller=null,cases=[],logs=[];
let evidenceReview=null,workspaceRows=[],workspaceStamp='',workspaceRequest=0,workspaceTimer=null,serviceState=null;
const fieldLabels={claim_number:'رقم المعاملة',policy_number:'رقم الوثيقة',claim_type:'نوع المطالبة',accident_date:'تاريخ الحادث',vehicle_plate:'رقم المركبة',incident_description:'وصف الحادث'};
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function reviewResult(c){try{return typeof c.result==='string'?JSON.parse(c.result):c.result||{}}catch{return {}}}
function toast(message){const el=$('toast');if(!el)return;el.textContent=message;el.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>{el.hidden=true},4500)}
const errorLabels={
 'Wait for the checked V2 report before recording review':'انتظر اكتمال تدقيق التقرير قبل تسجيل المراجعة.',
 'Complete or explicitly waive follow-up tasks and reanalyze role changes before approval':'أكمل مهام المتابعة أو وثّق تجاوزها، وحدّث التقرير بعد تغيير المستندات قبل اعتماد المراجعة.',
 'Written reason required':'اكتب سبب الإجراء أولًا.', 'Correction reason required':'اكتب سبب تحديث التقرير.',
 'Task changed; reload':'تغيّرت المهمة لدى طلب آخر. أعد تحميل حالتها قبل الحفظ.',
 'Stale case version':'صدر تحديث جديد للمعاملة. احتفظنا بما كتبته؛ افتح الإصدار الحالي قبل الحفظ.',
 'Stale analysis version':'الإصدار المعروض قديم. افتح الإصدار الحالي.',
 'Stale upload version':'صدر إصدار جديد أثناء الإرفاق. حدّث حالة المعاملة وأعد المحاولة.',
 'Document already uploaded':'هذا المستند موجود في المعاملة بالفعل.', 'Required role: supervisor':'تسجيل المراجعة يتطلب صلاحية المراجع.',
 'Supervisor account required':'هذا الإجراء متاح للمراجع فقط.', 'Only drafts accept documents':'لا يمكن إرفاق هذا الملف إلى مسودة أُرسلت سابقًا. افتح المتابعة لإضافة استكمال.',
 'Only review/failed cases accept supplements':'انتظر انتهاء المعالجة قبل إرفاق مستند استكمال.'
};
function userError(error){return errorLabels[error?.message]||error?.message||'تعذر إتمام الطلب. حاول مجددًا.'}
async function refresh(){const data=await api('/workspace/cases');workspaceRows=data.items;cases=workspaceRows;workspaceStamp=data.updated_at;return workspaceRows}
function isReviewer(){return accountSession?.user?.role==='admin'}
function badge(state){const names={draft:'مسودة',preparing:'قراءة المستندات',queued:'في الانتظار',processing:'فحص المعاملة',review:'تحتاج متابعة',approved:'مراجعة مسجلة',rejected:'مراجعة غير معتمدة',failed:'تعذرت المعالجة',DRAFT:'مسودة',PREPARING:'قراءة المستندات',QUEUED:'في الانتظار',PROCESSING:'فحص المعاملة',REPORT_PENDING:'تدقيق التقرير',UPDATE_REQUIRED:'التقرير يحتاج تحديثًا',FOLLOWUP_REQUIRED:'متطلبات مفتوحة',READY_FOR_REVIEW:'جاهزة للمراجعة',REVIEW_RECORDED:'مراجعتها مسجلة',FAILED:'تعذرت المعالجة'};return `<span class="status-tag state-${esc(String(state).toLowerCase())}">${esc(names[state]||state)}</span>`}
