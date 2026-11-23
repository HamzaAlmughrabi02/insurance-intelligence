// Standalone simulation: no requests to a private computer, n8n, or model provider.
const DEMO_KEY='intellisure-guided-demo-v1';let demoLogs=[],demoHistories={},sampleLoaded=false;
try{const saved=JSON.parse(sessionStorage.getItem(DEMO_KEY)||'null');if(saved){cases=saved.cases||[];demoLogs=saved.logs||[];demoHistories=saved.histories||{}}else cases=[]}catch{cases=[]}
connected=true;token='';
function saveDemo(){try{sessionStorage.setItem(DEMO_KEY,JSON.stringify({cases,logs:demoLogs,histories:demoHistories}))}catch{}}
function demoDocumentUrl(d){return DEMO_DOCUMENTS.find(x=>x.id===d.id)?.url||''}
function demoResult(fields={},version=1){return {analysis_type:'LOCAL_RULES_AND_DOCUMENT_EVIDENCE',claim_version:version,summary:'نتيجة محاكاة تعليمية: توجد ملاحظة غير محسومة حول إصلاح غطاء المحرك. قارن المصادر ثم راجع البيانات.',extracted:{claim_number:'INS-DEMO-001',policy_number:'POL-2026-10482',claim_type:'motor',accident_date:'2026-11-18',vehicle_plate:'TEST-4821',incident_description:'The vehicle slipped on a wet road and struck a roadside barrier. Hood causation remains uncertain.',...fields},flags:['HOOD_REPAIR_JOD_850_UNCERTAIN: compare invoice, incident report and inspection','DOCUMENT_EVIDENCE_REQUIRES_REVIEW','Policy source has not been verified.'],requires_human_review:true,final_claim_decision:null,evidence:DEMO_EVIDENCE}}
function logDemo(action){demoLogs.unshift({created_at:new Date().toISOString(),action,actor:'زائر التجربة',case_id:'INS-DEMO-001'})}
function loadDemoSample(){sampleLoaded=true;files=DEMO_DOCUMENTS.map(d=>({name:d.original_name,size:d.size,webkitRelativePath:''}));page='home';render();$('client').value='DEMO-CLIENT-001';$('kind').selectedIndex=1;toast('الملفات الاصطناعية الخمسة جاهزة. اضغط بدء التحليل.')}
submit=async function(){
 if(!sampleLoaded){toast('اضغط «استخدم الملفات الجاهزة» أولًا. هذه النسخة لا تحلل ملفات الزوار.');return}
 const client=$('client').value.trim()||'DEMO-CLIENT-001';busy=true;const btn=$('submit');btn.disabled=true;btn.textContent='جارٍ تشغيل المحاكاة…';
 await new Promise(resolve=>setTimeout(resolve,700));
 let c=cases.find(c=>c.id==='INS-DEMO-001');if(!c){c={id:'INS-DEMO-001',kind:'مطالبة مركبة · محاكاة',client,status:'review',created_at:new Date().toISOString(),documents:DEMO_DOCUMENTS,result:JSON.stringify(demoResult())};cases.unshift(c);demoHistories[c.id]=[{version:1,created_at:c.created_at,result:c.result}]}else c.client=client;
 logDemo('اكتملت محاكاة مراجعة الملفات الخمسة');saveDemo();busy=false;currentId=c.id;files=[];page='results';render();toast('ظهرت النتيجة التجريبية. اضغط ملاحظة غطاء المحرك لمراجعة مصادرها.')
};
api=async function(path,method='GET',body=null){
 if(path==='/cases'&&method==='GET')return cases;
 if(path==='/review-queue'&&method==='GET')return cases.filter(c=>c.status==='review').map(c=>{const r=typeof c.result==='string'?JSON.parse(c.result):c.result;return {id:c.id,kind:c.kind,client:c.client,status:c.status,created_at:c.created_at,document_count:c.documents?.length||0,policy_number:r?.extracted?.policy_number||'',claim_version:r?.claim_version||1,reasons:r?.flags||[],summary:r?.summary||''}});
 if(path==='/audit')return demoLogs;
 const parts=path.split('/'),id=decodeURIComponent(parts[2]||''),c=cases.find(x=>x.id===id);if(!c)throw Error('اختر الملفات الجاهزة وابدأ التجربة أولًا.');
 if(method==='GET'){
  if(parts[3]==='evidence')return DEMO_EVIDENCE;
  if(parts[3]==='history')return demoHistories[id]||[];
  return c;
 }
 if(parts[3]==='reanalyze'){
  if(!body?.note?.trim())throw Error('اكتب سبب التصحيح.');
  const old=JSON.parse(c.result),version=old.claim_version+1;
  c.result=JSON.stringify(demoResult({...old.extracted,...body.fields},version));c.status='review';
  (demoHistories[id]||=[]).push({version,created_at:new Date().toISOString(),result:c.result});logDemo('حفظ تصحيح وإصدار محاكاة '+version);saveDemo();return {status:'review'};
 }
 if(parts[3]==='review'){c.status=body.decision==='approve'?'approved':'rejected';logDemo('تسجيل إجراء مراجعة تجريبي فقط');saveDemo();return {status:c.status}}
 throw Error('هذا الإجراء غير متاح في العرض التجريبي.');
};
refresh=async function(){return cases};startPolling=function(){};
settingsPage=function(){return `<section class="card"><h2>عن هذه التجربة</h2><p class="review-summary">هذا عرض مستقل يعمل في متصفحك بمستندات اصطناعية جاهزة. لا يتصل بـn8n أو PostgreSQL المحلي، ولا يستدعي ذكاءً اصطناعيًا خارجيًا. نتائج التحليل وإعادة التحليل محاكاة تعليمية.</p><p>التغييرات تخص جلسة متصفحك؛ لا توجد بيانات مشتركة بين الزوار أو حسابات فعلية.</p><p><a href="https://github.com/HamzaAlmughrabi02/insurance-intelligence" target="_blank" rel="noopener">عرض المشروع والوركفلو على GitHub</a></p></section>`};
connect=function(){go('settings')};disconnect=function(){go('settings')};
function resetDemo(){cases=[];demoLogs=[];demoHistories={};files=[];sampleLoaded=false;currentId='';evidenceReview=null;reviewQueue=[];reviewQuery='';reviewCategory='all';reviewContext=false;reviewQueueRequest++;saveDemo();go('home');toast('بدأت جلسة تجربة جديدة.')}
// Uploaded visitor files are not read or transmitted. Use the supplied synthetic fixtures.
for(const id of ['fileinput','folderinput'])$(id).addEventListener('change',()=>{files=[];render();toast('للتجربة العامة استخدم المستندات الاصطناعية الجاهزة؛ لا ترفع وثائق حقيقية.')});
dropFiles=function(event){event.preventDefault();toast('هذه النسخة مخصصة للملفات الاصطناعية الجاهزة فقط.')};
const demoBaseRender=render;
render=function(){demoBaseRender();$('connection').textContent='Demo · محاكاة مستقلة';document.body.classList.remove('auth-pending');if($('submit'))$('submit').textContent='بدء التحليل التجريبي';};
const intro=document.createElement('section');intro.className='notice';intro.style.cssText='margin:0 0 24px;line-height:1.9;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap';intro.innerHTML='<div><strong>جرّب مراجعة مطالبة تأمين من البداية إلى الأدلة</strong><div>بيانات اصطناعية فقط · المعالجة محاكاة داخل المتصفح · لا اتصال بالخادم المحلي</div></div><div><button class="primary" onclick="loadDemoSample()">استخدم الملفات الجاهزة</button> <button class="ghost" onclick="resetDemo()">إعادة التجربة</button></div>';
document.querySelector('.heading').after(intro);render();restoreReviewRoute();
reviewQueueTimer=setInterval(()=>{if(page==='review')loadReviewQueue()},10000);
