const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const http = require("node:http");
const { spawn } = require("node:child_process");
const { initDb, confirmOptOut } = require("./outreach-db");

const launcher = path.resolve(__dirname, "../launch-campaign.js");

async function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "outreach-launch-flow-"));
  const runDir = path.join(root, "runs", "small-test");
  fs.mkdirSync(runDir, { recursive: true });
  const state = { campaign: null, leads: [], tags: [], calls: [],
    safeguardsReadable: true, membershipReadable: true, membershipReads: 0,
    membershipFailsAfter: Infinity, membershipDisconnects: false,
    pauseChangesStatus: true, activationChangesStatus: true };
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://mock");
    let text = "";
    for await (const chunk of req) text += chunk;
    const payload = text ? JSON.parse(text).payload : null;
    const route = url.pathname.replace("/outreach/instantly", "");
    state.calls.push({ method: req.method, route, payload });
    const send = (status, body) => { res.writeHead(status, { "content-type": "application/json" }); res.end(JSON.stringify(body)); };
    if (route === "/accounts") return send(200, { items: [{ email: "mailbox@cold.test", status: 1, daily_limit: 10,
      first_name: "Provider", last_name: "Name" }] });
    if (route === "/custom-tags" && req.method === "GET") return send(200, { items: state.tags });
    if (route === "/custom-tags" && req.method === "POST") {
      const tag = { id: `tag-${state.tags.length}`, ...payload }; state.tags.push(tag); return send(200, tag);
    }
    if (route === "/custom-tags/toggle-resource") {
      state.campaign.custom_tags = state.tags; return send(200, {});
    }
    if (route === "/campaigns" && req.method === "GET") return send(200, { items: state.campaign ? [state.campaign] : [] });
    if (route === "/campaigns" && req.method === "POST") {
      state.campaign = { id: "campaign-1", status: 0, ...payload }; return send(200, state.campaign);
    }
    if (route === "/campaigns/campaign-1" && req.method === "PATCH") {
      Object.assign(state.campaign, payload); return send(200, state.campaign);
    }
    if (route === "/campaigns/campaign-1" && req.method === "GET") {
      const result = { ...state.campaign, lead_stats: { total: state.leads.length, verified: state.leads.length,
        invalid: 0, pending_verification: 0 } };
      if (!state.safeguardsReadable) delete result.stop_on_reply;
      return send(200, result);
    }
    if (route === "/campaigns/campaign-1/activate") {
      if (state.activationChangesStatus) state.campaign.status = 1;
      return send(200, { status: 1 });
    }
    if (route === "/campaigns/campaign-1/pause") {
      if (state.pauseChangesStatus) state.campaign.status = 2;
      return send(200, { status: 2 });
    }
    if (route === "/leads" && req.method === "GET") {
      state.membershipReads++;
      if (state.membershipDisconnects) return req.socket.destroy();
      return state.membershipReadable && state.membershipReads <= state.membershipFailsAfter
        ? send(200, { items: state.leads }) : send(403, { error: "unreadable" });
    }
    if (route === "/leads/add") {
      const added = payload.leads.filter(lead => !state.leads.some(item => item.email === lead.email));
      state.leads.push(...added.map((lead, i) => ({ id: `lead-${state.leads.length + i}`, verification_status: 1, ...lead })));
      return send(200, { leads_uploaded: added.length });
    }
    return send(404, { error: `unexpected local mock route ${req.method} ${route}` });
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  t.after(() => { server.close(); fs.rmSync(root, { recursive: true, force: true }); });
  const spec = { run_key: "small-test", agent_id: "test-agent", product: { name: "Demo" },
    sender_name: "Explicit Sender", leads_file: "leads.json",
    campaign: { name: "Small permitted test", daily_limit: 3, email_list: ["mailbox@cold.test"],
      wait_for_verification: false, verify_leads_on_import: true,
      schedule: { name: "Test schedule", timing: { from: "09:00", to: "17:00" }, timezone: "Europe/Lisbon", days: { monday: true } } },
    monitoring: { thresholds: { max_bounce_rate: 2 } },
    sequence: { steps: [{ subject: "A useful option", body: "Hello,\n\nSee https://product.test/offer\n\nExplicit Sender", delay_days: 0 }] } };
  fs.writeFileSync(path.join(runDir, "leads.json"), JSON.stringify([{ email: "lead@buyer.test" }]));
  const execute = async () => {
    const specPath = path.join(runDir, "run-spec.json");
    fs.writeFileSync(specPath, JSON.stringify(spec));
    return new Promise(resolve => {
      const child = spawn(process.execPath, [launcher, "--run-spec", specPath], { cwd: runDir,
        env: { ...process.env, OS_URL: `http://127.0.0.1:${server.address().port}`, OS_API_KEY: "local-test" } });
      let stdout = "", stderr = "";
      child.stdout.on("data", chunk => { stdout += chunk; });
      child.stderr.on("data", chunk => { stderr += chunk; });
      child.on("close", status => resolve({ status, stdout, stderr }));
    });
  };
  return { runDir, spec, state, execute,
    summary: () => JSON.parse(fs.readFileSync(path.join(runDir, "launch-summary.json"))),
    activations: () => state.calls.filter(item => item.route.endsWith("/activate")) };
}

test("CLI accepts a small generic draft with a first-touch link and preserves sender choice", async t => {
  const f = await fixture(t);
  const result = await f.execute();
  assert.equal(result.status, 0, result.stderr);
  assert.equal(f.summary().launch_status, "draft");
  assert.equal(f.activations().length, 0);
  assert.equal(f.state.campaign.daily_limit, 3);
  assert.equal(f.state.campaign.open_tracking, false);
  assert.equal(f.summary().imported, 1);
  assert.match(f.state.campaign.sequences[0].steps[0].variants[0].body, /https:\/\/product\.test\/offer/);
  const resolved = JSON.parse(fs.readFileSync(path.join(f.runDir, "state", "resolved-run-spec.json")));
  assert.equal(resolved.reply_policy.sender_name, "Explicit Sender");
});

test("explicit activation requires confirmed readback and preserves first launch across reruns", async t => {
  const f = await fixture(t);
  f.spec.campaign.activate_on_launch = true;
  let result = await f.execute();
  assert.equal(result.status, 0, result.stderr);
  assert.equal(f.summary().activation.confirmed, true);
  const launchedAt = f.summary().launched_at;
  assert.ok(launchedAt);
  result = await f.execute();
  assert.equal(result.status, 0, result.stderr);
  assert.equal(f.summary().launched_at, launchedAt);
  assert.equal(f.state.leads.length, 1);
});

for (const missing of ["safeguardsReadable", "membershipReadable"]) {
  test(`missing ${missing} prevents activation`, async t => {
    const f = await fixture(t);
    f.spec.campaign.activate_on_launch = true;
    f.state[missing] = false;
    const result = await f.execute();
    assert.notEqual(result.status, 0);
    assert.equal(f.activations().length, 0);
  });
}

test("HTTP activation success cannot claim launched without active provider state", async t => {
  const f = await fixture(t);
  f.spec.campaign.activate_on_launch = true;
  f.state.activationChangesStatus = false;
  const result = await f.execute();
  assert.equal(result.status, 2, result.stderr);
  assert.equal(f.summary().activation.confirmed, false);
  assert.equal(f.summary().launch_status, "activation_unconfirmed");
  assert.equal(f.summary().launched_at, null);
});

test("an already imported confirmed opt-out cannot be reactivated", async t => {
  const f = await fixture(t);
  let result = await f.execute();
  assert.equal(result.status, 0, result.stderr);
  confirmOptOut(initDb(f.runDir), { run_key: "small-test", email: "lead@buyer.test", message_id: "message-1", campaign_id: "campaign-1" });
  f.spec.campaign.activate_on_launch = true;
  result = await f.execute();
  assert.equal(result.status, 2, result.stderr);
  assert.equal(f.summary().launch_status, "confirmed_opt_out_still_in_campaign");
  assert.equal(f.activations().length, 0);
  assert.equal(f.state.campaign.status, 2);
});

for (const disconnect of [false, true]) {
  test(`active rerun contains known refusals before aborting an unreadable membership (${disconnect ? "transport" : "HTTP"})`, async t => {
    const f = await fixture(t);
    f.spec.campaign.activate_on_launch = true;
    assert.equal((await f.execute()).status, 0);
    const before = f.state.calls.length;
    confirmOptOut(initDb(f.runDir), { run_key: "small-test", email: "lead@buyer.test",
      message_id: "refusal", campaign_id: "campaign-1" });
    f.state.membershipReadable = false;
    f.state.membershipDisconnects = disconnect;
    const result = await f.execute();
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /Cannot establish campaign membership/);
    assert.equal(f.state.campaign.status, 2);
    const calls = f.state.calls.slice(before);
    assert.equal(calls.filter(call => call.route.endsWith("/pause")).length, 1);
    assert.equal(calls.filter(call => call.route.endsWith("/activate") || call.route === "/leads/add").length, 0);
    const stop = f.summary().opt_out_stop_results[0];
    assert.equal(stop.ok, true);
    assert.equal(stop.campaigns[0].membership, "unknown");
    assert.equal(stop.campaigns[0].readback_status, 2);
    assert.ok(stop.checked_at);
  });
}

test("an unresolved refusal pause is retained when membership aborts the launch", async t => {
  const f = await fixture(t);
  f.spec.campaign.activate_on_launch = true;
  assert.equal((await f.execute()).status, 0);
  confirmOptOut(initDb(f.runDir), { run_key: "small-test", email: "lead@buyer.test",
    message_id: "refusal", campaign_id: "campaign-1" });
  f.state.membershipReadable = false;
  f.state.pauseChangesStatus = false;
  const result = await f.execute();
  assert.equal(result.status, 1);
  assert.match(result.stderr, /stopping .* is not confirmed/);
  assert.equal(f.state.campaign.status, 1);
  const stop = f.summary().opt_out_stop_results[0];
  assert.equal(stop.ok, false);
  assert.equal(stop.campaigns[0].action, "provider_action_unresolved");
  assert.equal(stop.campaigns[0].readback_status, 1);
});

test("membership lost at the final activation gate still contains an active run", async t => {
  const f = await fixture(t);
  f.spec.campaign.activate_on_launch = true;
  assert.equal((await f.execute()).status, 0);
  confirmOptOut(initDb(f.runDir), { run_key: "small-test", email: "lead@buyer.test",
    message_id: "refusal", campaign_id: "campaign-1" });
  // The early budget/import read succeeds; the final pre-activation read fails.
  f.state.membershipFailsAfter = f.state.membershipReads + 1;
  const activationsBefore = f.activations().length;
  const result = await f.execute();
  assert.equal(result.status, 2, result.stderr);
  assert.equal(f.summary().activation_blocked, "campaign_membership_unavailable");
  assert.equal(f.state.campaign.status, 2);
  assert.equal(f.activations().length, activationsBefore);
  assert.equal(f.summary().opt_out_stop_results[0].ok, true);
});

test("membership lost immediately before a new import still contains an active run", async t => {
  const f = await fixture(t);
  f.spec.campaign.activate_on_launch = true;
  assert.equal((await f.execute()).status, 0);
  confirmOptOut(initDb(f.runDir), { run_key: "small-test", email: "lead@buyer.test",
    message_id: "refusal", campaign_id: "campaign-1" });
  fs.writeFileSync(path.join(f.runDir, "leads.json"), JSON.stringify([
    { email: "lead@buyer.test" }, { email: "new@buyer.test" },
  ]));
  f.state.membershipFailsAfter = f.state.membershipReads + 1;
  const callsBefore = f.state.calls.length;
  const result = await f.execute();
  assert.equal(result.status, 1, result.stderr);
  assert.equal(f.state.campaign.status, 2);
  assert.equal(f.state.calls.slice(callsBefore).some(call =>
    call.route === "/leads/add" || call.route.endsWith("/activate")), false);
  assert.equal(f.summary().opt_out_stop_results[0].ok, true);
});
