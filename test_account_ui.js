const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=__dirname,html=fs.readFileSync(path.join(root,'index.html'),'utf8');
async function scenario(configured){
 const nodes=new Map(),requests=[];
 function element(){return {value:'',innerHTML:'',textContent:'',disabled:false,classList:{add(){},remove(){}},addEventListener(){},setAttribute(){},remove(){}}}
 const document={getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)},addEventListener(){},createElement:element,body:{classList:{add(){},remove(){}},append(){}}};
 const context=vm.createContext({document,window:{scrollTo(){}},location:{hash:configured?'':'#setup=synthetic-invite',pathname:'/',search:''},history:{replaceState(){}},URLSearchParams,setTimeout(){},setInterval(){},clearInterval(){},console,Blob,fetch:async(url,options={})=>{
  requests.push({url,options});const data=url.endsWith('/auth/status')?{setup_required:!configured}:url.endsWith('/auth/session')?{user:{username:'qa-owner',role:'admin'},csrf:'synthetic-csrf'}:url==='/api/cases'&&(!options.method||options.method==='GET')?[]:url.endsWith('/system/status')?{ready:true}:{};
  return {ok:true,status:200,json:async()=>data};
 }});
 Object.defineProperty(context,'localStorage',{get(){throw Error('Credentials must not use localStorage')}});
 Object.defineProperty(context,'sessionStorage',{get(){throw Error('Credentials must not use sessionStorage')}});
 for(const [,source] of html.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(source,context);
 await new Promise(resolve=>setImmediate(resolve));
 if(!configured){assert(nodes.get('account-entry').innerHTML.includes('إنشاء حسابك'));assert(nodes.get('account-entry').innerHTML.includes('confirmation'))}
 else{
  await vm.runInContext("api('/cases','POST',{kind:'motor',client:'synthetic'})",context);
  const call=requests.at(-1);assert.equal(call.options.credentials,'same-origin');assert.equal(call.options.headers['X-CSRF-Token'],'synthetic-csrf');assert(!('Authorization' in call.options.headers));
  assert(vm.runInContext('settingsPage()',context).includes('تسجيل الخروج'));
  assert(!vm.runInContext('settingsPage()',context).includes('id="token"'));
 }
 return true;
}
(async()=>{await scenario(false);await scenario(true);console.log('Account UI: setup screen, session restore, cookie API, CSRF, and token-free settings passed.');fs.writeFileSync(path.join(root,'account-ui-test-results.json'),JSON.stringify({status:'PASS',real_browser:false,checks:5},null,2))})().catch(e=>{console.error(e);process.exitCode=1});
