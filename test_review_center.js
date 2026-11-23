const fs=require('fs'),vm=require('vm'),assert=require('assert');
const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:''});return nodes.get(id)};
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ctx=vm.createContext({renderDetail:()=>'',resultPage:()=>'',loadDetail:async()=>{},go(){},render(){},window:{addEventListener(){}},connected:true,page:'review',currentId:'old',cases:[],history:{pushState(a,b,url){ctx.lastUrl=url}},location:{hash:''},console,$,esc,toast(){},api:async path=>{if(path.endsWith('bad'))throw Error('not found');return {id:'new-id',client:'NEW CLIENT',status:'review'}},setInterval(){},clearInterval(){}});
for(const filename of ['evidence-review.js','review-center.js'])vm.runInContext(fs.readFileSync(__dirname+'/'+filename,'utf8'),ctx);
const run=code=>vm.runInContext(code,ctx);
(async()=>{
 run(`reviewQueue=[{id:'INS-1',client:'<script>client</script>',kind:'motor',policy_number:'POL-1',document_count:5,created_at:'2026-11-23',reasons:['DOCUMENT_EVIDENCE_REQUIRES_REVIEW','HOOD_REPAIR_JOD_850_UNCERTAIN']}];renderQueueRows()`);
 assert(nodes.get('queue-results').innerHTML.includes('&lt;script&gt;'));
 assert(!nodes.get('queue-results').innerHTML.includes('<script>'));
 assert(nodes.get('queue-results').innerHTML.includes('إصلاح غطاء المحرك'));
 assert(!nodes.get('queue-results').innerHTML.includes('textarea'));
 run(`reviewQuery='does-not-exist';renderQueueRows()`);assert(nodes.get('queue-results').innerHTML.includes('لا توجد معاملات تطابق'));
 run(`reviewQuery='';reviewCategory='policy';renderQueueRows()`);assert(nodes.get('queue-results').innerHTML.includes('لا توجد معاملات تطابق'));
 await run(`openReviewCase('new-id')`);assert.equal(ctx.currentId,'new-id');assert.equal(ctx.lastUrl,'#review/new-id');assert.equal(ctx.cases[0].client,'NEW CLIENT');
 await run(`openReviewCase('bad')`);assert.equal(ctx.currentId,'new-id');
 console.log('Review queue: 10 assertions passed; identity, reasons, filtering, escaping and correct-case navigation.');
})().catch(e=>{console.error(e);process.exitCode=1});
