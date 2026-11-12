const test = require("node:test");
const assert = require("node:assert/strict");
const { buildCampaignPayload } = require("../launch-campaign");
test("authored follow-up subjects survive without a marketing override flag",()=>{
 const input={run_key:"run",campaign:{name:"Test",daily_limit:3,schedule:{name:"Week",timing:{from:"09:00",to:"17:00"},days:[1],timezone:"UTC"}},sequence:{steps:[{delay_days:0,subject:"First",body:"Hello"},{delay_days:2,subject:"",body:"Reminder"},{delay_days:3,subject:"A separate topic",body:"Details"}]}};
 const steps=buildCampaignPayload(input,["person@outbound.test"],"Pat").sequences[0].steps;
 assert.deepEqual(steps.map(s=>s.variants[0].subject),["First","","A separate topic"]);
 assert.deepEqual(steps.map(s=>s.delay),[2,3,0]);
});
