const intake=$('Normalize Webhook Input').first().json;if(!intake.web_integration)return [];
let analysis=null;try{analysis=$('Merge Analysis Results').first().json}catch{}
try{const saved=$('Save Preliminary Analysis').first().json.analysis_payload;if(saved&&typeof saved==='object'&&Object.keys(saved).length)analysis=saved}catch{}
const validation=$('Validate Claim Data').first().json.validation;
const result=analysis?{...analysis}:{summary:'المطالبة تحتاج تصحيح بيانات قبل التحليل.',findings:[],missing_information:validation?.completeness?.missing_fields??[],analysis_status:'REQUIRES_REVIEW'};
result.extracted=intake.claim_data;result.evidence=intake.evidence;result.field_sources=intake.field_sources??{};result.field_quality=intake.field_quality??{};result.repair_items=intake.repair_items??[];
result.flags=[...new Set([...(intake.document_flags??[]),...(validation?.completeness?.missing_fields??[]),...(validation?.warnings??[])])];
result.claim_version=intake.claim_version;result.requires_human_review=true;result.final_claim_decision=null;result.claim_status_changed=false;
return [{json:{case_id:intake.case_id,job_id:intake.job_id,result}}];
