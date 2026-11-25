const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=name=>fs.readFileSync(__dirname+'/'+name,'utf8');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}};
function harness(){
 const nodes=new Map(),listeners={},messages=[];
 const node=id=>({id,innerHTML:'',textContent:'',dataset:{},querySelectorAll(){return []},querySelector(){return null},focus(){},insertAdjacentHTML(){},scrollIntoView(){}});
 const ctx=vm.createContext({console,page:'results',currentId:'A',connected:true,cases:[],fieldLabels:{},renderDetail:()=>'',loadDetail:async()=>{},resultPage:()=>'',render(){},go(target){ctx.page=target},history:{pushState(a,b,url){ctx.route=url},replaceState(){}},location:{hash:'',pathname:'/',search:''},window:{addEventListener(){}},document:{title:'',activeElement:null,addEventListener(type,fn){listeners[type]=fn},querySelector(){return null},querySelectorAll(){return []}},$:id=>{if(!nodes.has(id))nodes.set(id,node(id));return nodes.get(id)},esc:v=>String(v??''),toast:m=>messages.push(m),api:async()=>({}),clearTimeout(){},setTimeout(){},setInterval(){},clearInterval(){},showAccountEntry(){},connect(){},refresh:async()=>{},startPolling(){},badge:()=>'',analysisStatus:()=>'',home:()=>'',table:()=>'',FormData:class{constructor(form){this.data=form?.values||{}}entries(){return Object.entries(this.data)}[Symbol.iterator](){return this.entries()[Symbol.iterator]()}get(k){return this.data[k]}}});
 const load=f=>vm.runInContext(source(f),ctx),run=s=>vm.runInContext(s,ctx);
 load('review-state.js');return {ctx,nodes,listeners,messages,load,run};
}
(async()=>{
 let h=harness();h.load('evidence-review.js');h.load('review-center.js');
 let a=deferred(),b=deferred();h.ctx.api=path=>path.endsWith('/A')?a.promise:b.promise;
 let pa=h.run("openReviewCase('A')"),pb=h.run("openReviewCase('B')");b.resolve({id:'B'});await pb;a.resolve({id:'A'});await pa;
 assert.equal(h.ctx.currentId,'B');assert.equal(h.ctx.route,'#review/B');
 a=deferred();h.ctx.api=()=>a.promise;pa=h.run("openReviewCase('A')");h.run("go('home')");a.resolve({id:'A'});await pa;assert.equal(h.ctx.page,'home');assert.equal(h.ctx.currentId,'B');
 console.log('PASS delayed case requests cannot override newer navigation');

 h=harness();h.load('v2-report.js');h.run('renderV2Report=()=>{};v2RestoreEvidenceSnapshot=()=>{};v2SyncReviewControls=()=>{}');
 a=deferred();b=deferred();h.ctx.api=path=>path.includes('history')?Promise.resolve([]):path.includes('?version=')?a.promise:b.promise;
 pa=h.run('v2OpenVersion(1)');pb=h.run("loadV2Report('A')");b.resolve({case_id:'A',version:2,status:'completed'});await pb;a.resolve({case_id:'A',version:1,status:'completed'});await pa;assert.equal(h.run('v2State.version'),2);
 a=deferred();b=deferred();h.ctx.api=path=>path.includes('history')?Promise.resolve([]):path.endsWith('=1')?a.promise:b.promise;pa=h.run('v2OpenVersion(1)');pb=h.run('v2OpenVersion(2)');b.resolve({case_id:'A',version:2});await pb;a.resolve({case_id:'A',version:1});await pa;assert.equal(h.run('v2State.version'),2);
 console.log('PASS explicit report and history requests invalidate older responses');

 h.run("v2State={case_id:'A',version:2,is_current:true};loadV2Report=async()=>{refreshCount++}");h.ctx.refreshCount=0;a=deferred();h.ctx.api=()=>a.promise;pa=h.run("v2Write('followup',{})");h.run("v2Request++;v2State={case_id:'A',version:1,is_current:false}");a.resolve({});await pa;assert.equal(h.ctx.refreshCount,0);
 a=deferred();h.run("v2State={case_id:'A',version:2,is_current:true}");h.ctx.api=()=>a.promise;pa=h.run("v2Write('followup',{})");h.run("go('home')");a.resolve({});await pa;assert.equal(h.ctx.refreshCount,0);
 console.log('PASS save completion preserves a newer historical view or route');

 h=harness();h.load('v2-report.js');h.run("v2State={case_id:'A',version:2,is_current:true,tasks:[{id:'t',revision:0}]};loadV2Report=async()=>{}");
 const taskForm={dataset:{draftEdit:'1',draftDirty:'true',taskRevision:'0'},values:{note:'first',state:'OPEN'},querySelector:()=>({disabled:false})};
 h.ctx.event={preventDefault(){},currentTarget:taskForm};let submitted=[];a=deferred();h.ctx.api=(path,method,body)=>{submitted.push(body);return a.promise};
 pa=h.run("v2SaveTask(event,'t')");taskForm.dataset.draftEdit='2';taskForm.values.note='typed while saving';a.resolve({status:'saved'});await pa;
 assert.equal(taskForm.dataset.draftDirty,'true');assert.equal(taskForm.dataset.taskRevision,'1');h.ctx.api=async(path,method,body)=>{submitted.push(body);return {status:'saved'}};
 await h.run("v2SaveTask(event,'t')");assert.equal(submitted[1].revision,1);assert.equal(submitted[1].note,'typed while saving');
 console.log('PASS edits made during a save retain draft values and acknowledged task revision');

 h=harness();h.load('evidence-review.js');h.run('renderEvidenceWorkspace=()=>{}');h.ctx.reviewResult=()=>({});const get=h.ctx.$;h.ctx.$=id=>id==='v2-report'?null:get(id);
 for(const suffix of ['/A','/evidence','/history']){
  h.ctx.api=async path=>{if(path.endsWith(suffix))throw Error('temporary outage');return path.endsWith('/A')?{id:'A'}:[]};
  await h.run("loadDetail('A')");assert(h.nodes.get('detail').innerHTML.includes('إعادة تحميل المعاملة'));assert(!h.nodes.get('detail').innerHTML.includes('جارٍ تحميل'));
 }
 h.ctx.api=async path=>path.endsWith('/A')?{id:'A',result:{}}:[];h.ctx.renderDetail=()=>'<p>recovered</p>';await h.run("loadDetail('A')");assert.equal(h.nodes.get('detail').innerHTML,'<p>recovered</p>');
 a=deferred();h.ctx.api=()=>a.promise;pa=h.run("loadDetail('A')");h.ctx.currentId='B';h.nodes.get('detail').innerHTML='B content';a.reject(Error('late failure'));await pa;assert.equal(h.nodes.get('detail').innerHTML,'B content');
 console.log('PASS each detail dependency failure exposes retry and stale errors are ignored');

 h=harness();const details={open:true},input={selectionStart:3,selectionEnd:3,focus(){h.ctx.document.activeElement=this},setSelectionRange(){}};
 const form=id=>({id,dataset:{draftDirty:'true',draftEdit:'1'},closest:()=>details,contains:x=>x===input,getAttribute:()=>'',replaceWith(old){this.restored=old}});
 const one=form('one'),two=form('two'),root={dataset:{},querySelectorAll(){return this.forms},forms:[one,two]};h.ctx.root=root;h.ctx.document.activeElement=input;
 h.run("reviewUI.useScope('A',2);reviewUI.restore(root);reviewUI.capture(root)");h.ctx.one=one;h.run("reviewUI.saved(one,'1')");const nextOne=form('one'),nextTwo=form('two');root.forms=[nextOne,nextTwo];h.run('reviewUI.restore(root)');assert.equal(nextOne.restored,undefined);assert.equal(nextTwo.restored,two);assert.equal(h.ctx.document.activeElement,input);
 h.run("reviewUI.useScope('B',2);reviewUI.restore(root)");const foreign=form('two');root.forms=[foreign];h.run('reviewUI.restore(root)');assert.equal(foreign.restored,undefined);
 h.run("reviewUI.useScope('A',2);reviewUI.restore(root);reviewUI.capture(root);reviewUI.clear()");const afterLogout=form('two');root.forms=[afterLogout];h.run('reviewUI.restore(root)');assert.equal(afterLogout.restored,undefined);
 const oldForm=form('shared'),newForm=form('shared');root.forms=[newForm];h.ctx.oldForm=oldForm;
 h.run("reviewUI.useScope('B',2);reviewUI.restore(root);reviewUI.capture(root);reviewUI.saved(oldForm,'1')");const replacement=form('shared');root.forms=[replacement];h.run('reviewUI.restore(root)');assert.equal(replacement.restored,newForm);
 console.log('PASS drafts preserve unrelated form nodes/focus and isolate cases/account exit');

 h=harness();h.load('ui-extension.js');a=deferred();h.ctx.api=()=>a.promise;let renders=0;h.ctx.render=()=>renders++;pa=h.run("retryCase('A')");h.run("currentId='B';go('results')");a.resolve({});await pa;assert.equal(h.ctx.currentId,'B');assert.equal(renders,0);
 console.log('PASS retry completion cannot restore an abandoned case');
})().catch(e=>{console.error(e);process.exitCode=1});
