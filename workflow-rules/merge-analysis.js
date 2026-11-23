const rules=$('Preliminary Analysis Engine').first().json;
const checked=$input.first().json,valid=checked.llm_validation?.valid===true,findings=[...(rules.findings??[])];
if(!valid)findings.push({code:'REPORT_FORMAT_FAILED',severity:'MEDIUM',message:'تعذر التحقق من تنسيق التقرير؛ تم الاحتفاظ بنتائج القواعد.',source:'SYSTEM'});
// The model's prose never upgrades facts/statuses. Only deterministic evidence-linked findings are authoritative here.
return [{json:{...rules,analysis_type:checked.provider==='LOCAL_RULES'?'LOCAL_RULES_AND_DOCUMENT_EVIDENCE':'RULES_WITH_UNVERIFIED_ADVISORY',
 analysis_status:valid?'COMPLETED':'REQUIRES_REVIEW',summary:rules.summary,findings,
 advisory:checked.provider==='LLM'&&valid?{text:checked.llm_analysis.summary,verification_status:'UNVERIFIED',source:'LLM'}:null,
 supervisor_questions:valid?checked.llm_analysis.supervisor_questions:[],llm_validation:checked.llm_validation,
 requires_human_review:true,final_claim_decision:null,claim_status_changed:false}}];
