const test=require("node:test"); const assert=require("node:assert/strict");
const {findLeadNameProblems,findLeadVariableProblems,leadNameChecksForSteps,deriveSenderName}=require("./helpers");
const {preflightLeadNames}=require("../launch-campaign");
test("cosmetic name heuristics warn but do not ban initials or capitals",()=>{
 for(const name of ["A","ANNA","AB"]) {
  const lead={email:"person@company.test",first_name:name};
  assert.equal(findLeadNameProblems([lead])[0].severity,"warning");
  assert.deepEqual(findLeadVariableProblems([{body:"Hello {{firstName}}"}],[lead]),[]);
  assert.doesNotThrow(()=>preflightLeadNames({sequence:{steps:[{body:"Hello {{firstName}}"}]}},[lead],"leads.json"));
 }
});
test("known title or credential is not silently used as a first name",()=>{
 for(const name of ["CA","Dr.","CPA","Mr"]) {
  const lead={email:"p@company.test",first_name:name};
  assert.equal(findLeadNameProblems([lead])[0].severity,"error");
  assert.equal(findLeadVariableProblems([{body:"Hello {{firstName}}"}],[lead]).length,1);
  assert.deepEqual(findLeadVariableProblems([{body:"Hello"}],[lead]),[]);
  assert.deepEqual(findLeadVariableProblems([{body:"Hello {{firstName}}"}],[{...lead,first_name_confirmed:true}]),[]);
 }
});
test("valid names across scripts and short mixed-case names stay usable",()=>{
 for(const name of ["Sheikh","Li","Wu","Jean-Luc","O'Brien","محمد","李"]) {
  assert.deepEqual(findLeadVariableProblems([{body:"{{firstName}}"}],[{email:"p@company.test",first_name:name}]),[]);
 }
});
test("long or capitalized company names warn instead of needing an override",()=>{
 for(const name of ["A".repeat(70),"BIG COMPANY"]) {
  const lead={email:"p@company.test",company_name:name};
  assert.equal(findLeadNameProblems([lead],{checkFirstName:false,checkCompanyName:true})[0].severity,"warning");
  assert.deepEqual(findLeadVariableProblems([{body:"{{companyName}}"}],[lead]),[]);
 }
});
test("only used missing fields block, including custom variables dropped by import",()=>{
 const leads=[{email:"p@company.test",first_name:""}];
 assert.deepEqual(findLeadVariableProblems([{body:"Hello"}],leads),[]);
 assert.equal(findLeadVariableProblems([{body:"{{firstName}} {{personalization}} {{custom}}"}],leads).length,3);
 const oversized=[{email:"p@company.test",custom:"x".repeat(1001)}];
 assert.equal(findLeadVariableProblems([{body:"{{custom}}"}],oversized).length,1);
});
test("actual custom values, zero, false and native aliases resolve",()=>{
 const lead={email:"p@company.test",firstName:"Pat",company_name:"ACME",custom_variables:{count:0,ready:false}};
 assert.deepEqual(findLeadVariableProblems([{body:"{{ firstName }} {{companyName}} {{count}} {{ready}}"}],[lead]),[]);
});
test("confirmed-name flag cannot turn an empty used value into valid output",()=>{
 assert.equal(findLeadVariableProblems([{body:"{{firstName}}"}],[{email:"p@company.test",first_name_confirmed:true}]).length,1);
});
test("rerun skips existing leads and ignores build-time sender token",()=>{
 const leads=[{email:"p@company.test"}]; const steps=[{body:"{{firstName}} {{senderName}}"}];
 assert.deepEqual(findLeadVariableProblems(steps,leads,{skipEmails:new Set(["p@company.test"])}),[]);
 assert.deepEqual(findLeadVariableProblems([{body:"{{senderName}}"}],leads),[]);
 assert.deepEqual(leadNameChecksForSteps([{body:"{{companyName}}"}]),{checkFirstName:false,checkCompanyName:true});
});
test("sender identity comes from actual account fields, never mailbox inference",()=>{
 assert.equal(deriveSenderName({email:"jane.smith@outbound.test"}),null);
 assert.equal(deriveSenderName({email:"different@outbound.test",firstName:"Pat",lastName:"Lee"}),"Pat Lee");
});
