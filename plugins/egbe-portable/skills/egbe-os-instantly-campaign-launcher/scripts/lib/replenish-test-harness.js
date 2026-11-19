// Shared fixtures for replenish-leads tests: a run dir with manifest, run-spec,
// carry-over and DB row, a mock OS outreach server, and the script runner.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const http = require("node:http");
const { spawn } = require("node:child_process");
const { initDb, upsertRun } = require("./outreach-db");

function makeRun(carryOver, prefix = "replenish-") {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  const runDir = path.join(root, "runs", "test");
  const stateDir = path.join(runDir, "state");
  fs.mkdirSync(stateDir, { recursive: true });
  const write = (name, value) => fs.writeFileSync(path.join(runDir, name), JSON.stringify(value));
  write("manifest.json", { run_key: "test-run", campaign: { id: "c", name: "test-campaign" } });
  write("run-spec.json", { product: { name: "test" }, segment: { name: "test" }, offer: { headline: "test" },
    lead_replenishment: { enabled: true, batch_size: 1, max_total_leads: 250,
      max_replenishments: 4, utilization_threshold: 0.8, cooldown_minutes: 0 } });
  write("state/carry-over-leads.json", carryOver);
  const dbPath = initDb(runDir);
  upsertRun(dbPath, { run_key: "test-run", product_name: "test", segment_name: "test", offer_headline: "test", campaign_id: "c", status: "launched" });
  return { root, runDir, stateDir, dbPath, cleanup: () => fs.rmSync(root, { recursive: true, force: true }) };
}

// handler(endpoint, req) returns { status = 200, data }, or null for a 400.
async function startServer(handler) {
  const srv = http.createServer((req, res) => {
    const reply = handler(req.url.split("?")[0], req);
    req.resume();
    res.writeHead(reply ? reply.status ?? 200 : 400, { "content-type": "application/json" });
    res.end(JSON.stringify({ data: reply?.data }));
  });
  await new Promise((resolve) => srv.listen(0, "127.0.0.1", resolve));
  return { url: `http://127.0.0.1:${srv.address().port}`, close: () => srv.close() };
}

function replenish(runDir, url, extraArgs = []) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(__dirname, "../replenish-leads.js"), "--run-dir", runDir, ...extraArgs], {
      env: { ...process.env, OS_API_KEY: "test", OS_URL: url },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", reject);
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

module.exports = { makeRun, startServer, replenish };
