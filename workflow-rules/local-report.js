const rules=$input.first().json;
return [{json:{provider:'LOCAL_RULES',text:JSON.stringify({summary:rules.summary,observations:[],missing_information:[],supervisor_questions:rules.findings?.length?['قارن الملاحظات بمصادرها الأصلية قبل تسجيل المراجعة.']:[],requires_human_review:true,final_claim_decision:null,claim_status_changed:false})}}];
