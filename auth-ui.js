// Local account UI. No API keys or session tokens are stored in browser storage.
let accountSession=null,setupTicket=new URLSearchParams(location.hash.slice(1)).get('setup')||'',setupRequired=false,servicesTimer=null;
if(location.hash.startsWith('#setup='))history.replaceState(null,'',location.pathname+location.search);
const existingRender=render;
render=function(){existingRender();if(accountSession){$('connection').textContent='متصل · '+accountSession.user.username;$('connection').setAttribute('title','جلسة دخول آمنة على هذا الجهاز')}};
const authErrors={
 'Incorrect username or password':'اسم المستخدم أو كلمة المرور غير صحيحين.',
 'Too many attempts. Try again in a few minutes.':'محاولات كثيرة؛ انتظر خمس دقائق ثم حاول مجددًا.',
 'Authentication is busy. Please try again.':'الدخول مشغول حاليًا؛ حاول بعد لحظات.',
 'Open the desktop launcher to set up your account':'افتح اختصار IntelliSure لإنشاء حسابك للمرة الأولى.',
 'Setup invitation expired. Open the desktop launcher again.':'انتهت صلاحية الإعداد. افتح اختصار المنصة مرة أخرى.',
 'Account already configured. Sign in.':'الحساب موجود بالفعل؛ استخدم تسجيل الدخول.',
 'Username needs 3–64 letters or numbers; password needs at least 12 characters':'اسم المستخدم من 3 إلى 64 حرفًا أو رقمًا، وكلمة المرور 12 حرفًا على الأقل.'
};
async function authRequest(path,obj){
 const r=await fetch('/api/auth/'+path,{method:obj===undefined?'GET':'POST',credentials:'same-origin',headers:obj===undefined?{}:{'Content-Type':'application/json',...(accountSession?{'X-CSRF-Token':accountSession.csrf}:{})},body:obj===undefined?undefined:JSON.stringify(obj)});
 const data=await r.json();if(!r.ok)throw Error(authErrors[data.error]||data.error||'تعذر الاتصال');return data;
}
function showAccountEntry(message=''){
 if(typeof reviewUI!=='undefined')reviewUI.clear();connected=false;cases=[];accountSession=null;clearInterval(poller);clearInterval(servicesTimer);
 document.body.classList.add('auth-pending');
 let panel=$('account-entry');if(!panel){panel=document.createElement('main');panel.id='account-entry';document.body.append(panel)}
 const setup=setupRequired;
 panel.innerHTML=`<section class="card" style="max-width:470px;margin:8vh auto;padding:28px"><p class="muted">IntelliSure · مساحة التأمين</p><h1 style="margin:14px 0">${setup?'إنشاء حسابك':'مرحبًا بعودتك'}</h1><p class="muted" style="line-height:1.8">${setup?'عيّن اسم مستخدم وكلمة مرور مرة واحدة. رموز ربط الخدمات تدار تلقائيًا.':'ادخل إلى معاملاتك ونتائج المراجعة. لا تحتاج إلى رمز API.'}</p>${setup&&!setupTicket?'<div class="notice" style="margin-top:18px">لبدء الإعداد، افتح اختصار IntelliSure V2 على سطح المكتب.</div>':`<form id="account-form" style="margin-top:20px"><label class="field">اسم المستخدم<input name="username" autocomplete="username" minlength="3" maxlength="64" required dir="auto"></label><label class="field" style="margin-top:14px">كلمة المرور<input name="password" type="password" autocomplete="${setup?'new-password':'current-password'}" ${setup?'minlength="12"':''} maxlength="256" required></label>${setup?'<label class="field" style="margin-top:14px">تأكيد كلمة المرور<input name="confirmation" type="password" autocomplete="new-password" minlength="12" maxlength="256" required></label><p class="muted" style="margin-top:8px">12 حرفًا على الأقل؛ يمكنك استخدام عبارة طويلة يسهل تذكرها.</p>':''}<label style="display:flex;align-items:center;gap:8px;margin:18px 0;font-size:14px"><input name="remember" type="checkbox" checked>تذكرني على هذا الجهاز لمدة 30 يومًا</label><p id="account-error" role="alert" style="line-height:1.8;margin:10px 0;color:var(--ink)">${esc(message)}</p><button class="primary" type="submit" style="width:100%">${setup?'إنشاء الحساب والدخول':'تسجيل الدخول'}</button></form>`}</section>`;
 const form=$('account-form');if(form)form.addEventListener('submit',submitAccount);
}
async function submitAccount(event){
 event.preventDefault();const form=event.currentTarget,data=new FormData(form),button=form.querySelector('button');
 if(setupRequired&&data.get('password')!==data.get('confirmation')){$('account-error').textContent='كلمتا المرور غير متطابقتين.';return}
 button.disabled=true;$('account-error').textContent='';
 try{
  const session=await authRequest(setupRequired?'setup':'login',{username:data.get('username'),password:data.get('password'),remember:data.has('remember'),...(setupRequired?{setup_ticket:setupTicket}:{})});
  form.reset();setupTicket='';setupRequired=false;await enterAccount(session);
 }catch(e){$('account-error').textContent=e.message;button.disabled=false}
}
async function enterAccount(session){
 intakeDraft={client:'',notes:''};pendingIntake.clear();accountSession=session;token='';connected=true;cases=[];logs=[];files=[];currentId='';page='home';
 await refresh();document.body.classList.remove('auth-pending');$('account-entry')?.remove();render();startPolling();checkServices();
 clearInterval(servicesTimer);servicesTimer=setInterval(checkServices,10000);
}
api=async function(path,method='GET',body=null,headers={}){
 const h={...headers};delete h.Authorization;delete h['X-Role'];
 if(method!=='GET')h['X-CSRF-Token']=accountSession?.csrf||'';
 let raw=body;if(body&&!(body instanceof Blob)){h['Content-Type']='application/json';raw=JSON.stringify(body)}
 const response=await fetch('/api'+path,{method,headers:h,body:raw,credentials:'same-origin'});const data=await response.json();
 if(response.status===401){showAccountEntry('انتهت الجلسة. سجّل الدخول من جديد.');throw Error('انتهت جلسة الدخول')}
 if(!response.ok)throw Error(data.error||'تعذر إتمام الطلب');return data;
};
disconnect=async function(){
 try{await authRequest('logout',{});intakeDraft={client:'',notes:''};pendingIntake.clear();files=[];showAccountEntry()}catch(e){toast('تعذر تسجيل الخروج؛ حاول مجددًا.')}
};
connect=function(){showAccountEntry()};
settingsPage=function(){return `<div class="two"><section class="card"><h2>الحساب</h2><div class="kv"><span>اسم المستخدم</span><b>${esc(accountSession?.user.username||'')}</b></div><div class="kv"><span>الصلاحية</span><b>${accountSession?.user.role==='admin'?'مدير ومراجع':'مشغل'}</b></div><p class="muted" style="margin:16px 0">يُحفظ دخولك بجلسة خاصة بهذا المتصفح. رموز الربط الداخلية لا تحتاج إلى إدخالها هنا.</p><button class="ghost" onclick="disconnect()">تسجيل الخروج</button></section><section class="card"><h2>جاهزية المعالجة</h2><div id="services-status" class="notice">جارٍ التحقق من الخدمات المحلية…</div><p class="muted" style="margin-top:15px">الاستخدام مخصص لهذا الكمبيوتر. تظل النتيجة الأولية بحاجة إلى مراجعتك.</p></section></div>`};
const accountRender=render;
render=function(){accountRender();if(page==='settings')checkServices()};
async function checkServices(){
 if(!accountSession)return;
 try{
  const status=await api('/system/status');
  const detail=status.ready?'الخدمات المحلية متاحة لاستقبال المطالبات.':!status.n8n_reachable?'جارٍ انتظار تشغيل محرك المعالجة n8n…':!status.database_port_reachable?'قاعدة بيانات المعالجة غير متاحة بعد…':!status.document_reader_reachable?'قارئ الصور والمستندات غير متاح. افتح اختصار IntelliSure V2 لإعادة تشغيله.':'رابط استقبال الوركفلو غير جاهز؛ تحقق من نشره وتشغيله في n8n.';
  if($('services-status'))$('services-status').textContent=detail;
  if($('submit')){$('submit').disabled=!status.ready||busy;$('submit').title=detail}
 }catch{}
}
const accountSubmit=submit;
submit=async function(){
 try{const status=await api('/system/status');if(!status.ready){toast('الخدمات لم تجهز بعد. انتظر قليلًا وافحص صفحة الإعدادات.');return}await accountSubmit()}catch(e){toast(e.message)}
};
downloadEvidence=async function(id,name){
 try{
  const r=await fetch('/api/documents/'+encodeURIComponent(id),{credentials:'same-origin'});if(!r.ok)throw Error('تعذر تحميل المستند');
  const filename=r.headers.get('Content-Disposition')?.match(/filename\*=UTF-8''(.+)/i);
  const url=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=url;a.download=filename?decodeURIComponent(filename[1]):(name||'document');document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
 }catch(e){toast(e.message)}
};
(async()=>{
 document.body.classList.add('auth-pending');
 try{
  const status=await authRequest('status');setupRequired=status.setup_required;
  if(setupRequired){showAccountEntry();return}
  try{await enterAccount(await authRequest('session'))}catch{showAccountEntry()}
 }catch{showAccountEntry('تعذر الوصول إلى الخادم. افتح اختصار تشغيل المنصة وحاول مجددًا.')}
})();
