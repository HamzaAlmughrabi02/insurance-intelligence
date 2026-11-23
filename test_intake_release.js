const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/index.html','utf8'),start=html.indexOf('async function submit(){'),end=html.indexOf('function startPolling(){',start),source=html.slice(start,end);
const fields={kind:{value:'motor'},client:{value:'QA'},notes:{value:'synthetic'},submit:{disabled:false,textContent:''}};
let creates=0,uploads=0,submits=0,failOnce=true,arabicHeader='';
const ctx=vm.createContext({$:id=>fields[id],files:[{name:'وثيقة.pdf',size:100,lastModified:1},{name:'invoice.pdf',size:100,lastModified:2}],connected:true,busy:false,page:'home',currentId:'',pendingIntake:new Map(),intakeDraft:{client:'QA',notes:'synthetic'},toast(){},confirm:()=>true,render(){},go(p){ctx.page=p},startPolling(){},refresh:async()=>{},console,api:async(path,method,body,headers)=>{
 if(path==='/cases'){creates++;return {id:'QA-1'}}
 if(path.endsWith('/documents')){uploads++;if(body.name==='وثيقة.pdf')arabicHeader=headers['X-Filename'];if(body.name==='invoice.pdf'&&failOnce){failOnce=false;throw Error('Synthetic network interruption')}return {}}
 if(path.endsWith('/submit')){submits++;return {status:'preparing'}}
 return {status:'draft'};
}});vm.runInContext(source,ctx);
(async()=>{await vm.runInContext('submit()',ctx);assert.equal(creates,1);assert.equal(ctx.files.length,2);assert.equal(submits,0);assert.equal(decodeURIComponent(arabicHeader),'وثيقة.pdf');assert(/^[\x00-\x7F]+$/.test(arabicHeader));
 await Promise.all([vm.runInContext('submit()',ctx),vm.runInContext('submit()',ctx)]);assert.equal(creates,1,'Retry must reuse draft');assert.equal(uploads,3,'Already-uploaded first file must not be uploaded twice');assert.equal(submits,1,'Double click must not submit twice');assert.equal(ctx.files.length,0);assert.equal(ctx.busy,false);console.log('Intake release: Arabic filenames, interrupted upload recovery and duplicate-click prevention passed.');})().catch(e=>{console.error(e);process.exitCode=1});
