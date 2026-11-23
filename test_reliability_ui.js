const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();function $(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'written review reason',scrollIntoView(){}});return elements.get(id)}
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const calls=[];const c={id:'CASE-1',status:'review',current_version:3,result:JSON.stringify({claim_version:3,field_quality:{policy_number:{status:'OBSERVED'}},policy_verification:{coverage_status:'UNVERIFIED'}})};
const ctx=vm.createContext({renderDetail:()=>'',reviewResult:c=>JSON.parse(c.result),fieldLabels:{policy_number:'رقم الوثيقة'},decide(){},loadDetail:async()=>{},currentId:'CASE-1',page:'results',connected:true,evidenceReview:{case:c,documents:[{id:'doc-1'}],evidence:[{document_id:'doc-1',pages:[{page:1,text:'safe'}]}]},selectEvidence(){},refresh:async()=>{},render(){},toast(){},$,esc,console,clearTimeout(){},setTimeout(){},FormData:class{get(){return 'policy number'}},api:async(path,method,body)=>{calls.push({path,method,body});return {answer:'<script>unsafe</script>',notice:'unverified',citations:[{document_id:'doc-1',page:1,quote:'<img src=x>'}]}}});
vm.runInContext(fs.readFileSync(__dirname+'/reliability-ui.js','utf8'),ctx);
const run=code=>vm.runInContext(code,ctx);
(async()=>{
 const html=run(`renderDetail(${JSON.stringify(c)})`);assert(html.includes('لم يُتحقق'));assert(html.includes('مساعد المراجع'));assert(!html.includes('التغطية مؤكدة'));
 const button={disabled:false};ctx.event={preventDefault(){},currentTarget:{querySelector:()=>button}};
 await run('askReviewAssistant(event)');assert.equal(calls[0].path,'/cases/CASE-1/assistant');assert.equal(button.disabled,false);assert($('assistant-answer').innerHTML.includes('&lt;script&gt;'));assert(!$('assistant-answer').innerHTML.includes('<script>'));assert($('assistant-answer').innerHTML.includes('&lt;img'));
 await run("decide('CASE-1','approve')");assert.equal(calls.at(-1).body.version,3);assert.equal(calls.at(-1).body.note,'written review reason');
 console.log('Reliability UI: 10 source escaping, scope, unknown status and versioned-review assertions passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
