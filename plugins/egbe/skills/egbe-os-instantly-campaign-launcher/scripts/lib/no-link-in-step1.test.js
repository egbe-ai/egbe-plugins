const test = require("node:test");
const assert = require("node:assert/strict");
const { buildCampaignPayload } = require("../launch-campaign");
function spec(body) { return {run_key:"test", campaign:{name:"test",daily_limit:3,schedule:{name:"test",timing:{from:"09:00",to:"17:00"},days:[1,2,3,4,5],timezone:"UTC"}}, sequence:{steps:[{subject:"A relevant resource",body}]}}; }
test("first-message link is preserved without silently enabling trackers", () => {
 for (const body of ["See https://product.test/demo", "See [demo](https://product.test/demo)"]) {
  const payload = buildCampaignPayload(spec(body), ["person@outbound.test"], "Pat");
  assert.ok(payload.sequences[0].steps[0].variants[0].body.includes("https://product.test/demo"));
  assert.equal(payload.open_tracking,false); assert.equal(payload.link_tracking,false);
 }
});
test("generic copy is valid and explicit tracking is honored", () => {
 const input=spec("A useful invitation for a small audience."); input.campaign.open_tracking=true;
 const payload=buildCampaignPayload(input,["person@outbound.test"],"Pat");
 assert.equal(payload.open_tracking,true); assert.match(payload.sequences[0].steps[0].variants[0].body,/useful invitation/);
});
