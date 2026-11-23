const input=$input.first().json,verification=input.policy_verification??{},intake=$('Normalize Webhook Input').first().json;
const findings=[...(intake.document_findings??[])],missing=[];
const add=(code,severity,message)=>findings.push({code,severity,message,source:'RULE',verification_status:'RECORDED_CHECK'});
const documentMessages={FIELD_CONFLICT:'توجد قيم متعارضة لحقل مستخرج؛ يحتاج تصحيحًا موثقًا.',CONFLICTING_POLICY_NUMBERS:'توجد أرقام وثائق مختلفة أو رقم مصحح لا يطابق النص المقروء.',OCR_LOW_CONFIDENCE:'قراءة إحدى الصفحات منخفضة الثقة؛ قارنها بالأصل.',OCR_UNAVAILABLE:'تعذرت القراءة الآلية لإحدى الصفحات.',OCR_PAGE_LIMIT:'تجاوز المستند حد الصفحات المعالجة آليًا.',DOCUMENT_EVIDENCE_REQUIRES_REVIEW:'تتضمن المستندات معلومات غير محسومة تحتاج مقارنة بالمصادر.',CONTEXT_MODEL_UNAVAILABLE:'لم تتوفر مساعدة النموذج البصري؛ استُخدمت القراءة والقواعد المتاحة.',INCIDENT_DESCRIPTIONS_DIFFER:'توجد أوصاف مختلفة للحادث؛ قارنها في سياقها.'};
for(const flag of intake.document_flags??[]){const code=String(flag).split(':')[0];if(documentMessages[code]&&!findings.some(f=>f.code===code))add(code,['FIELD_CONFLICT','CONFLICTING_POLICY_NUMBERS'].includes(code)?'HIGH':code==='CONTEXT_MODEL_UNAVAILABLE'?'LOW':'MEDIUM',documentMessages[code])}
if(!verification.policy_found)add('POLICY_NOT_FOUND','MEDIUM','لم يُعثر على سجل الوثيقة؛ هذا لا يثبت عدم وجودها.');
if(!verification.source_verified||!verification.source_reference||!verification.source_verified_at){add('UNVERIFIED_POLICY_SOURCE','MEDIUM','مصدر الوثيقة لم يكتمل توثيقه.');missing.push('توثيق مصدر الوثيقة وتاريخ التحقق')}
if(verification.policy_status!=='ACTIVE')add('POLICY_STATUS_REQUIRES_REVIEW','MEDIUM','حالة الوثيقة غير مؤكدة كوثيقة فعّالة.');
if(verification.date_check==='OUTSIDE_POLICY_PERIOD')add('DATE_OUTSIDE_POLICY_PERIOD','HIGH','تاريخ الحادث خارج فترة الوثيقة المسجلة؛ يحتاج تحققًا بشريًا.');
if(verification.date_check!=='WITHIN_POLICY_PERIOD')missing.push('التحقق من تاريخ الحادث وفترة الوثيقة');
for(const [key,label] of [['vehicle_check','مطابقة المركبة'],['type_check','مطابقة نوع التأمين']]){
 if(verification[key]==='MISMATCH')add('POLICY_'+key.toUpperCase()+'_MISMATCH','HIGH',label+' غير متطابقة مع السجل.');
 else if(verification[key]!=='MATCH')missing.push(label+' مع سجل الوثيقة');
}
missing.push('مراجعة شروط التغطية والاستثناءات لدى المختص','التحقق البشري من المستندات الأصلية');
return [{json:{schema_version:'1.0',job_id:input.job_id,claim_id:input.claim_id,claim_version:input.claim_version,
 claim_context:{claim_type:input.claim_type,policy_number:input.policy_number,accident_date:input.accident_date,incident_description:input.incident_description},
 policy_verification:verification,analysis_type:'RULE_BASED_PRELIMINARY',analysis_status:'COMPLETED',
 summary:'اكتملت الفحوص الأولية. النتائج تبيّن الملاحظات وما لم يُتحقق منه؛ لا تمثل قرار تغطية أو دفع.',
 findings,missing_information:[...new Set(missing)],recommendation:'REFER_TO_HUMAN_REVIEW',requires_human_review:true,
 final_claim_decision:null,claim_status_changed:false,analyzed_at:new Date().toISOString()}}];
