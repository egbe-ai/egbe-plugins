const test=require("node:test"); const assert=require("node:assert/strict");
const {initialBatchLimit,replenishmentConfig,validateLaunchConfig}=require("./run-config");
const config={enabled:true,batch_size:7,max_total_leads:11,max_replenishments:2,utilization_threshold:.6,cooldown_minutes:60};
test("no hidden batch limit without enabled replenishment",()=>{assert.equal(initialBatchLimit({},0,260),260);assert.equal(initialBatchLimit({lead_replenishment:{enabled:false}},0,3),3)});
test("explicit batch and lifetime cap both apply",()=>{const s={lead_replenishment:config};assert.equal(initialBatchLimit(s,0,50),7);assert.equal(initialBatchLimit(s,9,50),2);assert.equal(initialBatchLimit(s,11,50),0)});
test("unknown counts and incomplete replenishment configuration do not invent defaults",()=>{assert.throws(()=>initialBatchLimit({lead_replenishment:config},null,50));assert.throws(()=>replenishmentConfig({lead_replenishment:{enabled:true}}));});
test("small daily limit is valid; activation requires explicit protection",()=>{assert.doesNotThrow(()=>validateLaunchConfig({campaign:{daily_limit:2}}));assert.throws(()=>validateLaunchConfig({campaign:{daily_limit:2,activate_on_launch:true}}));assert.doesNotThrow(()=>validateLaunchConfig({campaign:{daily_limit:2,activate_on_launch:true},monitoring:{thresholds:{max_bounce_rate:1}}}));});
