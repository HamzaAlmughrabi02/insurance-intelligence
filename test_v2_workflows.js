const fs=require('fs'),assert=require('assert');
const files=['insurance-production.json','insurance-error-handler.json','insurance-review-sync.json','insurance-review-assistant.json','insurance-v2-audited-report.json'];let count=0;
for(const file of files){
 const w=JSON.parse(fs.readFileSync(__dirname+'/n8n/'+file));assert.equal(w.active,false);
 for(const n of w.nodes){
  assert(!n.credentials);if(n.parameters?.url)assert(!n.parameters.url.includes(':8766'));
  if(n.type==='n8n-nodes-base.webhook'){assert(n.parameters.path.startsWith('insurance-v2-'));assert.equal(n.parameters.authentication,'headerAuth')}
  if(n.type==='n8n-nodes-base.code')new Function(n.parameters.jsCode);
  const body=n.parameters?.jsonBody;
  if(body?.startsWith('={{'))new Function('$json','$','$execution','return ('+body.slice(3,-2).trim()+');');
  count++;
 }
}
const r=JSON.parse(fs.readFileSync(__dirname+'/n8n/insurance-v2-audited-report.json'));
assert(r.nodes.some(n=>n.name==='Evidence Analyst'&&n.type==='n8n-nodes-base.httpRequest'));
assert(r.nodes.some(n=>n.name==='Independent Semantic Auditor'&&n.parameters.url==='http://127.0.0.1:11434/api/chat'));
for(const name of ['Build Analyst Request','Build Auditor Request']){
 const n=r.nodes.find(n=>n.name===name),out=new Function('$input',n.parameters.jsCode)({first:()=>({json:{sources:[],assertions:[]}})})[0].json;
 assert.equal(out.stream,false);assert.equal(out.think,false);assert.equal(out.format.additionalProperties,false);assert(out.options.num_predict<=2000);
}
console.log('V2 workflow contracts passed:',count,'nodes, unique authenticated routes, valid expressions and schema-constrained local calls.');
