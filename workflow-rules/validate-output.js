const item=$input.first().json,errors=[];let parsed;
try{const raw=item.text??item.output;parsed=typeof raw==='string'?JSON.parse(raw.trim().replace(/^```(?:json)?\s*/i,'').replace(/\s*```$/,'')):raw}catch{errors.push('INVALID_JSON')}
const keys=['summary','observations','missing_information','supervisor_questions','requires_human_review','final_claim_decision','claim_status_changed'];
if(!parsed||typeof parsed!=='object'||Array.isArray(parsed))errors.push('OBJECT_REQUIRED');
else {
 if(keys.some(k=>!Object.hasOwn(parsed,k))||Object.keys(parsed).some(k=>!keys.includes(k)))errors.push('INVALID_KEYS');
 if(typeof parsed.summary!=='string'||!parsed.summary.trim()||parsed.summary.length>3000)errors.push('INVALID_SUMMARY');
 if(!Array.isArray(parsed.observations)||parsed.observations.length>5)errors.push('INVALID_OBSERVATIONS');
 else for(const o of parsed.observations)if(!o||typeof o.description!=='string'||!o.description.trim()||o.description.length>2000||!['CLAIM_CLARIFICATION','VERIFICATION_GAP','REPORTED_AMOUNT_DISCREPANCY','INPUT_INTEGRITY'].includes(o.category)||!['LOW','MEDIUM','HIGH'].includes(o.severity)){errors.push('INVALID_OBSERVATION');break}
 for(const key of ['missing_information','supervisor_questions'])if(!Array.isArray(parsed[key])||parsed[key].length>5||parsed[key].some(v=>typeof v!=='string'||!v.trim()||v.length>1000))errors.push('INVALID_'+key);
 if(parsed.requires_human_review!==true||parsed.final_claim_decision!==null||parsed.claim_status_changed!==false)errors.push('INVALID_DECISION_BOUNDARY');
}
return [{json:{llm_validation:{valid:!errors.length,errors,scope:'STRUCTURE_ONLY_NOT_FACT_VERIFICATION',validated_at:new Date().toISOString()},llm_analysis:errors.length?null:parsed,provider:item.provider==='LOCAL_RULES'?'LOCAL_RULES':'LLM'}}];
