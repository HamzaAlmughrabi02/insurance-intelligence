const data=$input.first().json, claim=data.claim_data;
const missing=[],warnings=[];
const string=(value,name,max=100)=>{if(typeof value!=='string'||!value.trim()||value.length>max)missing.push(name)};
for(const key of ['schema_version','event_id','event_type','job_id','claim_id','correlation_id','occurred_at'])string(data[key],key);
if(!claim||typeof claim!=='object'||Array.isArray(claim))missing.push('claim_data');
else {
 for(const [key,max] of Object.entries({claim_number:100,policy_number:100,claim_type:50,accident_date:10,vehicle_plate:50,incident_description:10000}))string(claim[key],'claim_data.'+key,max);
 if(claim.claim_number!==data.claim_id)warnings.push('CLAIM_ID_MISMATCH');
 if(claim.claim_type!=='motor')warnings.push('UNSUPPORTED_CLAIM_TYPE');
 const date=claim.accident_date;
 if(typeof date!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(date)||Number.isNaN(Date.parse(date))||new Date(date).toISOString().slice(0,10)!==date)warnings.push('INVALID_ACCIDENT_DATE');
 else if(date>new Date().toISOString().slice(0,10))warnings.push('FUTURE_ACCIDENT_DATE');
}
if(data.schema_version!=='1.0')warnings.push('UNSUPPORTED_SCHEMA');
if(data.event_type!=='claim.submitted')warnings.push('UNEXPECTED_EVENT_TYPE');
if(!Number.isInteger(data.claim_version)||data.claim_version<1)warnings.push('INVALID_CLAIM_VERSION');
if(typeof data.occurred_at!=='string'||!/^\d{4}-\d\d-\d\dT/.test(data.occurred_at)||Number.isNaN(Date.parse(data.occurred_at)))warnings.push('INVALID_EVENT_TIMESTAMP');
return [{json:{...data,validation:{valid:!missing.length&&!warnings.length,completeness:{complete:!missing.length,missing_fields:missing},warnings,requires_human_review:!!(missing.length||warnings.length),scope:'SCHEMA_AND_CONSISTENCY_NOT_TRUTH',claim_status_changed:false}}}];
