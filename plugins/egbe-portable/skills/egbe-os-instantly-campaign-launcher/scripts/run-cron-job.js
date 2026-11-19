#!/usr/bin/env node
// Bound each direct scheduler tick and fail closed on concurrent/stale locks.
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const { parseArgs } = require("./lib/helpers");
const scripts = {reply:"reply-worker.js", monitor:"monitor-campaign.js",
  replenish:"replenish-leads.js", conclude:"conclude-campaign.js"};

function main() {
  const args = parseArgs(process.argv);
  const script = scripts[args.job];
  const timeout = Number(args["timeout-seconds"]);
  if (!script || !args["run-dir"] || !args["env-file"] || !Number.isInteger(timeout)
      || timeout < 1 || timeout > 1800) throw new Error("Invalid cron job arguments");
  const runDir = path.resolve(args["run-dir"]);
  const lock = path.join(runDir, `.cron-${args.job}.lock`);
  try { fs.mkdirSync(lock, {mode:0o700}); }
  catch (err) {
    if (err.code !== "EEXIST") throw err;
    throw new Error(`Concurrent or stale job lock: ${lock}. Verify no tick is running before removing it.`);
  }
  try {
    fs.writeFileSync(path.join(lock, "owner.json"), JSON.stringify({pid:process.pid, started_at:new Date().toISOString()}));
    const result = spawnSync(process.execPath, [path.join(__dirname, script),
      "--run-dir", runDir, "--env-file", path.resolve(args["env-file"])],
      {stdio:"inherit", timeout:timeout * 1000, killSignal:"SIGKILL"});
    if (result.error) throw result.error;
    process.exitCode = result.status === null ? 1 : result.status;
  } finally { fs.rmSync(lock, {recursive:true, force:true}); }
}
try { main(); } catch (err) { console.error(err.message); process.exitCode = 1; }
