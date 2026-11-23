const request=$('Prepare Policy Verification Request').first().json;
const claim=$('Normalize Webhook Input').first().json.claim_data;
const policy=$input.first()?.json??{},found=policy.policy_found===true,reasons=[];
const validDate=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&!Number.isNaN(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
const norm=v=>String(v??'').toUpperCase().replace(/[\s-]/g,'');
const sourceAudited=found&&policy.source_verified===true&&typeof policy.source_reference==='string'&&!!policy.source_reference.trim()&&!!policy.verified_at&&!Number.isNaN(Date.parse(policy.verified_at))&&Date.parse(policy.verified_at)<=Date.now();
let dateCheck='UNVERIFIED',vehicle='NOT_VERIFIED',type='NOT_VERIFIED';
if(!found)reasons.push('POLICY_NOT_FOUND');
else {
 if(policy.policy_status!=='ACTIVE')reasons.push('POLICY_NOT_CONFIRMED_ACTIVE');
 if(policy.source_verified!==true)reasons.push('POLICY_SOURCE_NOT_VERIFIED');
 if(!sourceAudited)reasons.push('POLICY_SOURCE_AUDIT_MISSING');
 if(!validDate(request.accident_date)||!validDate(policy.effective_date)||!validDate(policy.expiry_date)||policy.effective_date>policy.expiry_date)reasons.push('INVALID_OR_MISSING_DATES');
 else if(request.accident_date>=policy.effective_date&&request.accident_date<=policy.expiry_date)dateCheck='WITHIN_POLICY_PERIOD';
 else{dateCheck='OUTSIDE_POLICY_PERIOD';reasons.push('ACCIDENT_OUTSIDE_POLICY_PERIOD')}
 if(policy.insured_vehicle_plate){vehicle=norm(policy.insured_vehicle_plate)===norm(claim.vehicle_plate)?'MATCH':'MISMATCH';if(vehicle==='MISMATCH')reasons.push('POLICY_VEHICLE_MISMATCH')}
 else reasons.push('POLICY_VEHICLE_NOT_VERIFIED');
 if(policy.policy_claim_type){type=policy.policy_claim_type===claim.claim_type?'MATCH':'MISMATCH';if(type==='MISMATCH')reasons.push('POLICY_TYPE_MISMATCH')}
 else reasons.push('POLICY_TYPE_NOT_VERIFIED');
}
return [{json:{...request,policy_found:found,policy_status:found?policy.policy_status:'MISSING',source_verified:sourceAudited,
 source_reference:policy.source_reference??null,source_verified_at:policy.verified_at??null,checked_at:new Date().toISOString(),
 effective_date:policy.effective_date??null,expiry_date:policy.expiry_date??null,date_check:dateCheck,vehicle_check:vehicle,type_check:type,
 verification_status:reasons.length?'REQUIRES_REVIEW':'RECORDED_CHECKS_MATCH',coverage_status:'UNVERIFIED',evidence_status:'UNVERIFIED',
 requires_human_review:reasons.length>0,review_reasons:reasons,claim_status_changed:false}}];
