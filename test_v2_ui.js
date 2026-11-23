const fs=require('fs'),vm=require('vm'),assert=require('assert');
const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',querySelectorAll(){return []},focus(){}});return nodes.get(id)};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const calls=[],ctx=vm.createContext({resultPage:()=>'',renderDetail:()=>'',loadDetail:async()=>{},showAccountEntry(){},document:{title:'',querySelector(){return null},querySelectorAll(){return []}},$,esc,reviewResult:c=>c.result,fieldLabels:{policy_number:'رقم الوثيقة'},currentId:'QA',page:'results',clearTimeout(){},setTimeout(){},console,toast(){},api:async(path,method,data)=>{calls.push({path,method,data});return ctx.fixture},FormData:class{},accountSession:{csrf:'test-only'}});
vm.runInContext(fs.readFileSync(__dirname+'/v2-report.js','utf8'),ctx);const run=s=>vm.runInContext(s,ctx);
const source={document_name:'<script>bad</script>',document_id:'doc',page:1,quote:'<img src=x>',evidence_id:'ev',readable:true};
ctx.fixture={case_id:'QA',version:2,is_current:true,status:'completed',stage:'PUBLISHED',tasks:[{id:'task',title:'استكمال فحص',reason:'<script>x</script>',kind:'MISSING_DOCUMENT',state:'OPEN',evidence_ids:[],owner:'',due_date:'',note:'',revision:2}],history:[{version:1,updated_at:'yesterday'},{version:2,updated_at:'today'}],changes:{previous_version:1,fields:[{field:'policy_number',before:'POL-OLD',after:'POL-NEW'}],findings_added:[],findings_removed:[],previous_read_pages:1,read_pages:2},report:{quality_state:'PARTIAL',decision_notice:'Preliminary',sources:{ev:source},coverage:{complete:false,read_pages:1,total_pages:2,documents:[{document_id:'doc',name:'scan.pdf',complete:false,observed_pages:1,expected_pages:2,pages:[{page:1,status:'PARTIAL'}]}]},documents:[{id:'doc',role:'inspection',name:'scan.pdf'}],findings:[{id:'f',text:'<script>finding</script>',severity:'HIGH',origin:'DETERMINISTIC_CHECK',evidence_ids:['ev']}],model_assertions:[],withheld:[{text:'rejected claim',reason:'unsupported'}],comparisons:[],invoice_rows:[],generated_at:'today',schema_version:'2',model_status:'REVIEW_COMPLETED',model_name:'local',execution_id:'123'}};
run('v2State=fixture;renderV2Report()');assert($('v2-report').innerHTML.includes('قراءة غير مكتملة'));assert(!$('v2-report').innerHTML.includes('<script>finding'));assert($('v2-report').innerHTML.includes('&lt;script&gt;finding'));assert($('v2-report').innerHTML.includes('report-print?version=2'));
run("v2ChooseTab('findings')");assert($('v2-report').innerHTML.includes('محجوبة'));assert($('v2-report').innerHTML.includes('&lt;script&gt;bad'));
run("v2ChooseTab('tasks')");assert($('v2-report').innerHTML.includes('task'));assert($('v2-report').innerHTML.includes('&lt;script&gt;x'));assert(!$('v2-report').innerHTML.includes('<script>x'));
run("v2ChooseTab('history')");assert($('v2-report').innerHTML.includes('POL-OLD'));assert($('v2-report').innerHTML.includes('POL-NEW'));assert($('v2-report').innerHTML.includes('v2OpenVersion(1)'));
run("v2ChooseTab('coverage')");assert($('v2-report').innerHTML.includes('قراءة جزئية'));assert($('v2-report').innerHTML.includes('اقتراح آلي'));
run("v2State.status='running';v2State.report=null;v2State.stage='VERIFIER';renderV2Report()");assert($('v2-report').innerHTML.includes('تدقيق المعنى'));assert(!$('v2-report').innerHTML.includes('99%'));
console.log('V2 UI: 16 assertions passed: report navigation, escaping, coverage, exact source links, version history and real stages.');

// Regression: the UI must mirror approval gates and display the requested evidence snapshot.
const approve={disabled:false,title:'',getAttribute(){return "decide('QA','approve')"}},reject={disabled:false,title:'',getAttribute(){return "decide('QA','reject')"}};
ctx.document.querySelectorAll=selector=>selector==='#review-resolution button'?[approve,reject]:[];
run("v2State=fixture;v2State.is_current=true;v2State.status='completed';v2SyncReviewControls()");assert(approve.disabled);assert(!reject.disabled);assert(approve.title.includes('الاستكمال'));
run("v2State.tasks=[];v2State.role_changes_pending=true;v2SyncReviewControls()");assert(approve.disabled);assert(approve.title.includes('تصنيفها'));
run("v2State.role_changes_pending=false;v2SyncReviewControls()");assert(!approve.disabled);
ctx.evidenceReview={case_id:'QA',case:{result:{evidence:[{document_id:'doc',pages:[{text:'CURRENT'}]}]}},evidence:[]};ctx.renderEvidenceWorkspace=()=>{};
ctx.snapshotHistory=[{version:1,result:JSON.stringify({evidence:[{document_id:'doc',pages:[{text:'HISTORICAL'}]}]})}];
run("v2RestoreEvidenceSnapshot({case_id:'QA',version:1,is_current:false},snapshotHistory)");assert.equal(ctx.evidenceReview.evidence[0].pages[0].text,'HISTORICAL');
run("v2RestoreEvidenceSnapshot({case_id:'QA',version:2,is_current:true})");assert.equal(ctx.evidenceReview.evidence[0].pages[0].text,'CURRENT');
console.log('Release regressions: approval gates, historic evidence and current snapshot restoration passed.');
