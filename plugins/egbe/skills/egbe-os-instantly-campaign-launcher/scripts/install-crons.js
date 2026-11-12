#!/usr/bin/env node
// install-crons — Install run-scoped cron jobs for an Instantly campaign run.
//
// Schedulers: OpenClaw cron (default) or explicit --scheduler cron on an always-on host.
// Each job is registered as an `agentTurn` payload that triggers an OpenClaw agent
// with a tightly-scoped message asking it to run exactly one script and report.
//
// Unix cron runs the bundled scripts directly without an agent turn.
//
// Usage:
//   node install-crons.js --run-dir <path> --env-file <path> [--scheduler openclaw|cron] [--dry-run]
//     [--deliver-channel <channel> --deliver-to <target> | --no-chat-delivery] [--agent <id>]
//
// OpenClaw agent: --agent <id> (must exist on the host), else the agent whose
// workspace holds --run-dir, else the host's default agent from
// `openclaw agents list --json`. Agent ids differ per host (e.g. "fina"), so
// the installer never assumes "main". A reinstall keeps the recorded agent.
//
// OpenClaw delivery: isolated cron sessions have no "last" chat route, so the
// installer requires an explicit target (flags, or notifications.deliver_channel
// / notifications.deliver_to in run-spec.json) or --no-chat-delivery.
//
// Send window (OpenClaw only): reply and monitor run only around the campaign's
// sending schedule (campaign.schedule in run-spec.json), in its timezone.

const fs = require("fs");
const path = require("path");
const { createHash, randomUUID } = require("crypto");
const os = require("os");
const { execFileSync } = require("child_process");
const {
  readJson,
  writeJson,
  parseArgs,
  isoNow,
  readEnvFile,
  ensureRunEnv,
  getOsConfig,
} = require("./lib/helpers");

function shellQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function hasBinary(name) {
  try {
    execFileSync("which", [name], {
      stdio: ["ignore", "pipe", "ignore"],
      timeout: 5000,
    });
    return true;
  } catch {
    return false;
  }
}

// OpenClaw drops a final reply that is exactly this token instead of
// delivering it, so a quiet tick posts nothing to the owner's chat.
const SILENT_TOKEN = "NO_REPLY";

// 24/7 cadence used when the run spec has no usable sending schedule.
// Reply runs hourly at :05 so it never coincides with the monitor at :15.
const DEFAULT_SCHEDULES = { reply: "5 * * * *", monitor: "15 * * * *" };
const WINDOW_MARGIN_BEFORE_MINUTES = 60;
const WINDOW_MARGIN_AFTER_MINUTES = 120;

function parseClock(value) {
  const match = /^(\d{1,2}):(\d{2})$/.exec(String(value || "").trim());
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 24 || minutes > 59 || (hours === 24 && minutes)) return null;
  return hours * 60 + minutes;
}

// Day keys are numeric 0=Sun..6=Sat (Instantly's own format) or weekday
// names. Any numeric key marks the map numeric, so a Tue-Fri map without
// "0"/"1" keys is not misread as a name map (which would mean every day).
function sendingDays(days) {
  if (!days) return [0, 1, 2, 3, 4, 5, 6];
  const names = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
  const numeric = Object.keys(days).some((key) => /^[0-6]$/.test(key));
  return names
    .map((name, index) => (numeric ? days[String(index)] : days[name]) ? index : null)
    .filter((index) => index != null);
}

function cronDayField(days) {
  if (days.length === 7) return "*";
  const parts = [];
  for (let i = 0; i < days.length; i++) {
    let j = i;
    while (j + 1 < days.length && days[j + 1] === days[j] + 1) j++;
    parts.push(j - i >= 2 ? `${days[i]}-${days[j]}` : days.slice(i, j + 1).join(","));
    i = j;
  }
  return parts.join(",");
}

function validTimezone(tz) {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

// Derive reply/monitor cron expressions from campaign.schedule: same days,
// from one hour before the window opens until two hours after it closes, in
// the campaign's timezone. Anything unusable keeps the 24/7 cadence.
function deriveSendWindow(runSpec) {
  const schedule = runSpec?.campaign?.schedule;
  const fallback = (reason) => ({ applied: false, reason, timezone: "UTC", ...DEFAULT_SCHEDULES });
  if (!schedule) return fallback("run spec has no campaign.schedule; keeping the 24/7 cadence");
  const tz = schedule.timezone;
  const from = parseClock(schedule.timing?.from);
  const to = parseClock(schedule.timing?.to);
  if (!tz || from == null || to == null) {
    return fallback("campaign.schedule needs timezone and timing.from/to (HH:MM); keeping the 24/7 cadence");
  }
  if (!validTimezone(tz)) return fallback(`campaign.schedule.timezone "${tz}" is not a valid IANA zone; keeping the 24/7 cadence`);
  if (to <= from) return fallback("sending windows that cross midnight are not supported; keeping the 24/7 cadence");
  const days = sendingDays(schedule.days);
  if (!days.length) return fallback("campaign.schedule.days has no sending day; keeping the 24/7 cadence");
  const startHour = Math.max(0, Math.floor((from - WINDOW_MARGIN_BEFORE_MINUTES) / 60));
  // Last hourly tick lands in the hour two hours after close (17:00 -> 19:xx).
  const endHour = Math.min(23, Math.floor((to + WINDOW_MARGIN_AFTER_MINUTES) / 60));
  const hours = startHour === endHour ? String(startHour) : `${startHour}-${endHour}`;
  const dow = cronDayField(days);
  return {
    applied: true,
    timezone: tz,
    sending: { from: schedule.timing.from, to: schedule.timing.to, days },
    margin_minutes: { before: WINDOW_MARGIN_BEFORE_MINUTES, after: WINDOW_MARGIN_AFTER_MINUTES },
    hours,
    days_of_week: dow,
    reply: `5 ${hours} * * ${dow}`,
    monitor: `15 ${hours} * * ${dow}`,
  };
}

function stringOption(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

// Where OpenClaw delivers the agent's final reply for each job.
function resolveDelivery(args, runSpec) {
  if (args["no-chat-delivery"]) {
    return { mode: "none", source: "--no-chat-delivery", flags: ["--no-deliver"] };
  }
  const notifications = runSpec?.notifications || {};
  const argChannel = stringOption(args["deliver-channel"]);
  const argTo = stringOption(args["deliver-to"]);
  const channel = argChannel || stringOption(notifications.deliver_channel);
  const to = argTo || stringOption(notifications.deliver_to);
  if (!channel || !to) {
    return {
      mode: "missing",
      error:
        "OpenClaw cron jobs need an explicit chat delivery target: isolated cron sessions have no " +
        '"last" chat route, so reports and alerts would be silently dropped. Pass ' +
        "--deliver-channel <channel> --deliver-to <target> (e.g. --deliver-channel slack " +
        "--deliver-to channel:C0123456789), or set notifications.deliver_channel and " +
        "notifications.deliver_to in run-spec.json, or pass --no-chat-delivery to run without chat reports." +
        (channel || to ? ` Got only ${channel ? "a channel" : "a target"}; both are required.` : ""),
    };
  }
  return {
    mode: "announce",
    channel,
    to,
    source: argChannel && argTo ? "args" : argChannel || argTo ? "args + run-spec notifications" : "run-spec notifications",
    flags: ["--announce", "--channel", channel, "--to", to],
  };
}

function readOpenclawAgents() {
  let out;
  try {
    out = execFileSync("openclaw", ["agents", "list", "--json"], {
      encoding: "utf8",
      timeout: 15000,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (err) {
    const detail = String(err.stderr || "").trim() || String(err.message);
    throw new Error(`Cannot read OpenClaw agents (openclaw agents list --json): ${detail}`);
  }
  let parsed;
  try { parsed = JSON.parse(out || "[]"); }
  catch { throw new Error(`Unexpected output from openclaw agents list --json: ${String(out).slice(0, 200)}`); }
  const agents = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.agents) ? parsed.agents : null;
  if (!agents) throw new Error(`Unexpected output from openclaw agents list --json: ${String(out).slice(0, 200)}`);
  return agents.filter((a) => a && typeof a.id === "string" && a.id);
}

function realpathOr(p) {
  try { return fs.realpathSync(p); } catch { return path.resolve(p); }
}

function insideDir(child, parent) {
  const rel = path.relative(parent, child);
  return rel === "" || (!!rel && !rel.startsWith("..") && !path.isAbsolute(rel));
}

// Which OpenClaw agent runs the jobs. A job for an agent the host does not
// have never runs, and one OpenClaw can hold several agents, so: --agent
// (must exist on the host), else the agent whose workspace holds the run
// directory, else the host's default (or only) agent. A reinstall without
// --agent never moves jobs recorded for another agent.
function resolveAgent(args, runDir, priorAgentId) {
  if (args.agent === true) throw new Error("--agent needs an agent id");
  const explicit = stringOption(args.agent);
  let agents;
  try { agents = readOpenclawAgents(); }
  catch (err) {
    if (!explicit) throw new Error(`${err.message}; pass --agent <id>`);
    // A broken agents list must not block an operator who names the agent.
    console.error(`WARNING: --agent ${explicit} not checked against the host's agents. ${err.message}`);
    return { id: explicit, source: "--agent (unverified)" };
  }
  const ids = agents.map((a) => a.id);
  if (explicit) {
    if (!ids.includes(explicit)) {
      throw new Error(`OpenClaw agent "${explicit}" is not on this host (agents: ${ids.join(", ") || "none"})`);
    }
    return { id: explicit, source: "--agent" };
  }
  const owners = agents
    .filter((a) => typeof a.workspace === "string" && a.workspace)
    .map((a) => ({ agent: a, real: realpathOr(a.workspace) }))
    .filter((o) => insideDir(runDir, o.real))
    .sort((a, b) => b.real.length - a.real.length)
    .map((o) => o.agent);
  let chosen;
  if (owners.length) chosen = { id: owners[0].id, source: "run-dir workspace" };
  else {
    const fallback = agents.find((a) => a.isDefault === true) || (agents.length === 1 ? agents[0] : null);
    if (!fallback) {
      throw new Error(`No default OpenClaw agent on this host (agents: ${ids.join(", ") || "none"}); pass --agent <id>`);
    }
    chosen = { id: fallback.id, source: fallback.isDefault === true ? "openclaw default agent" : "only openclaw agent" };
  }
  if (priorAgentId && priorAgentId !== chosen.id) {
    throw new Error(
      `This run's jobs were installed for agent "${priorAgentId}", but it now resolves to "${chosen.id}" (${chosen.source}). ` +
        `Pass --agent ${priorAgentId} to keep them there, or --agent ${chosen.id} to move them.`,
    );
  }
  return chosen;
}

// Unix cron runs in the host timezone and per-entry timezones are not
// portable, so the window applies to OpenClaw (which takes --tz) only.
function sendWindowFor(runSpec, scheduler) {
  if (scheduler === "cron") {
    return {
      applied: false,
      reason: "--scheduler cron runs in the host timezone (no portable per-entry timezone); keeping the 24/7 cadence",
      timezone: "host",
      ...DEFAULT_SCHEDULES,
    };
  }
  return deriveSendWindow(runSpec);
}

function jobsForRun(runDir, envFile, runSpec, sendWindow, scheduler) {
  const snapshotSchedule = runSpec.monitoring?.snapshot_schedule;
  if (snapshotSchedule !== undefined &&
      (typeof snapshotSchedule !== "string" || !/^[\d*,/\-]+(?: +[\d*,/\-]+){4}$/.test(snapshotSchedule)))
    throw new Error("monitoring.snapshot_schedule must contain five numeric cron fields, without commands or newlines");
  const base = path.dirname(path.resolve(__filename));
  const replenishEnabled =
    runSpec.lead_replenishment?.enabled === true;
  const windowTz = sendWindow.timezone;
  const fixedTz = scheduler === "cron" ? "host" : "UTC";

  const jobs = [
    {
      key: "reply",
      schedule: sendWindow.reply,
      tz: windowTz,
      timeout_seconds: 600,
      script: "reply-worker.js",
      intent:
        "Collect new inbound replies for this run into reply-queue.json, then answer or route each pending one.",
      agent_steps: [
        "Before deciding how to respond, read the project's current email-outreach method and this run's plan/reply policy. Use the current task's authority and product facts, not a new policy from this schedule.",
        "After the command, read reply-queue.json in the run directory and handle every item with status \"pending\" by references/reply-handling.md (read it first).",
        "To send a reply you wrote: save the text to a file and run `node send-reply.js --run-dir <run dir> --env-file <env file> --email-id <id> --text-file <file>` from the scripts directory.",
        "If a reply needs the owner, route it through the agreed channel with the original reply and your proposed response, then use `--mark owner_review`.",
        "After reading a reply, record a confirmed refusal with `--mark opt_out`; this also checks stopping known campaigns. Use `--mark no_reply` only for other messages needing no response, such as an automatic reply. A keyword hint alone is not confirmation.",
        "Handle one message at a time; never run two send-reply.js at once. An item still \"sending\" was interrupted mid-send: check its thread in Instantly, then run send-reply.js with `--mark sent` or `--mark pending`.",
      ],
      report_rules: [
        "- Report each reply you sent, routed to the owner, or marked, one line each. No new or pending replies is not news.",
      ],
    },
    {
      key: "monitor",
      schedule: sendWindow.monitor,
      tz: windowTz,
      timeout_seconds: 900,
      script: "monitor-campaign.js",
      intent:
        "Fetch campaign-scoped observations and apply the configured operational protection thresholds. Missing required signals are not healthy results; inspect the returned pause/readback state.",
      report_rules: [
        '- The command logs to cron-monitor.log; read monitor-summary.json in the run directory. Report only the items in "alerts" whose "alert" is "new", and "pause_action" if present (a pause was attempted this run).',
        '- If "pause_failed" is true, lead with it: pause is not confirmed. Inspect the provider state; a request response alone does not establish that sending stopped.',
        '- Items with "alert": "repeat" were already reported (including gates the owner acknowledged by resuming the campaign): do not mention them again. "pause_skipped" (campaign already paused), "pause_suppressed" (acknowledged gates) and "protection.skipped_gates" are not news.',
      ],
    },
  ];

  if (replenishEnabled) {
    jobs.push({
      key: "replenish",
      schedule: "45 */2 * * *",
      tz: fixedTz,
      timeout_seconds: 1800,
      script: "replenish-leads.js",
      intent:
        "Source the next batch of leads from carry-over or OS Apollo when utilization >= threshold and cooldown has elapsed. Import into the campaign.",
      report_rules: [
        '- The command logs to cron-replenish.log; its result is the last JSON there. Report when leads were imported.',
        '- If the result has "leads_rejected_names" > 0, that is news even when "skipped" is true: report the count and its "warning" text, and point the owner to "rejected_leads_file" (state/rejected-leads.json) in the run directory.',
        '- Otherwise "skipped": true (cooldown, cap, nothing to source) is not news.',
      ],
    });
  }

  // A factual export is optional. It does not decide that a test is finished.
  if (runSpec.monitoring?.snapshot_schedule) jobs.push({
    key: "conclude",
    schedule: runSpec.monitoring.snapshot_schedule,
    tz: fixedTz,
    timeout_seconds: 900,
    script: "conclude-campaign.js",
    intent: "Package the latest observed facts as conclusion.json; preserve source timestamps, nulls and partial coverage. This command does not assess the test or mark it complete.",
    report_rules: [
      '- Inspect collection errors and freshness. A newly packaged old snapshot is not new evidence; do not announce a business verdict from it.',
    ],
  });

  return jobs.map((job) => ({
    ...job,
    schedule_basis: ["reply", "monitor"].includes(job.key) && sendWindow.applied ? "send-window" : "fixed",
    base,
    command: `cd ${shellQuote(base)} && node ${job.script} --run-dir ${shellQuote(runDir)} --env-file ${shellQuote(envFile)} >> ${shellQuote(path.join(runDir, `cron-${job.key}.log`))} 2>&1`,
  }));
}

function jobName(runKey, key) {
  return `instantly-${runKey}-${key}`;
}

function buildAgentMessage(job, runKey, runDir) {
  return [
    `Scheduled cron job for instantly-campaign-launcher run "${runKey}".`,
    "",
    job.agent_steps ? "Execute this command first:" : "Execute this command, then report according to the rules below:",
    "",
    `  ${job.command}`,
    "",
    `Intent: ${job.intent}`,
    ...(job.agent_steps ? ["", "Then:", ...job.agent_steps.map((s) => `- ${s}`)] : []),
    "",
    "Reporting rules:",
    "- Do not start unrelated tasks. Do not modify files outside the run directory.",
    job.agent_steps
      ? `- Keep reply drafts under ${runDir}/replies/; the scripts write their own state.`
      : `- The script writes its own state under ${runDir}; you do not need to write anything else.`,
    "- If the script exits non-zero, report the exit code and the last error line.",
    ...(job.report_rules || []),
    `- Silent rule: when nothing needs the owner (no reply answered or routed, no new alert, no pause, no error), your final reply must be exactly ${SILENT_TOKEN} and nothing else; OpenClaw then delivers nothing. Otherwise send a short report of a few lines.`,
  ].join("\n");
}

// ---------------------------------------------------------------------------
// OpenClaw cron path (canonical)
// ---------------------------------------------------------------------------

function listOpenclawJobs(strict = false) {
  try {
    const out = execFileSync("openclaw", ["cron", "list", "--json", "--all"], {
      encoding: "utf8",
      timeout: 15000,
      stdio: ["ignore", "pipe", "pipe"],
    });
    const parsed = JSON.parse(out || "[]");
    if (Array.isArray(parsed)) return parsed;
    if (Array.isArray(parsed.jobs)) return parsed.jobs;
    if (strict) throw new Error("Invalid OpenClaw job list; cannot verify removal");
    return [];
  } catch (err) {
    if (strict) throw err;
    return [];
  }
}

function jobTargetsRun(job, runDir) {
  const message = job?.payload?.message;
  if (typeof message !== "string") return false;
  // Inspect the generated command, not the human-readable run key: different
  // workspaces can use the same key and therefore the same scheduler job name.
  const argument = ` --run-dir ${shellQuote(runDir)} --env-file `;
  return message.split("\n").some(line => line.startsWith("  cd ") && line.includes(argument));
}

function recordedJobIds(record, key, name) {
  return new Set((record.jobs || [])
    .filter(job => job.key === key || job.name === name)
    .flatMap(job => job.ids || []).map(String));
}

function findExistingJobs(allJobs, name, runDir, recordedIds = new Set()) {
  return allJobs.filter(job =>
    (job?.name === name || job?.id === name || recordedIds.has(String(job?.id))) &&
    jobTargetsRun(job, runDir));
}

function reconcileOpenclawJobs(runDir, runKey, jobs, record) {
  const existing = listOpenclawJobs(true);
  const recordedIds = new Set((record.jobs || []).flatMap(job => job.ids || []).map(String));
  for (const job of existing) {
    if (recordedIds.has(String(job.id)) && !jobTargetsRun(job, runDir)) {
      throw new Error(`Cannot verify recorded OpenClaw job ${job.id} belongs to this exact run directory; preserve the receipt and reconcile it before reinstalling`);
    }
  }
  const names = new Set(["reply", "monitor", "replenish", "conclude"].map(key => jobName(runKey, key)));
  const wantedNames = new Set(jobs.map(job => jobName(runKey, job.key)));
  const wantedIds = new Set(jobs.flatMap(job => [...recordedJobIds(record, job.key, jobName(runKey, job.key))]));
  const obsolete = job => jobTargetsRun(job, runDir) &&
    (names.has(job.name) || recordedIds.has(String(job.id))) &&
    !wantedNames.has(job.name) && !wantedIds.has(String(job.id));
  const removed = [];
  for (const job of existing.filter(obsolete)) {
    if (!job.id) throw new Error(`Cannot safely remove OpenClaw job ${job.name} without its stable ID`);
    execFileSync("openclaw", ["cron", "remove", String(job.id)], {timeout:15000, stdio:"pipe"});
    removed.push(String(job.id));
  }
  if (listOpenclawJobs(true).some(job => removed.includes(String(job.id)) || obsolete(job))) {
    throw new Error("OpenClaw reconciliation failed: omitted jobs remain; preserve the previous receipt and retry removal");
  }
  return removed;
}

function openclawCronUpsert(job, runKey, runDir, delivery, agent, record) {
  const name = jobName(runKey, job.key);
  const message = buildAgentMessage(job, runKey, runDir);
  const allJobs = listOpenclawJobs(true);
  const existing = findExistingJobs(allJobs, name, runDir, recordedJobIds(record, job.key, name));

  if (existing.length > 0) {
    // Dedupe defensively: keep the first match, edit it, delete the rest.
    // Without this, a previously-buggy state with multiple jobs of the same
    // name would have all of them re-edited, leaving N copies firing.
    const keep = existing[0];
    const keepId = keep.id || keep.name;
    execFileSync(
      "openclaw",
      [
        "cron",
        "edit",
        String(keepId),
        "--agent",
        agent.id,
        "--name",
        name,
        "--cron",
        job.schedule,
        "--tz",
        job.tz,
        "--session",
        "isolated",
        "--message",
        message,
        ...delivery.flags,
        "--enable",
        "--timeout-seconds",
        String(job.timeout_seconds),
      ],
      { stdio: ["ignore", "pipe", "pipe"], timeout: 15000 },
    );
    const removed = [];
    for (const dup of existing.slice(1)) {
      const dupId = dup.id || dup.name;
      try {
        execFileSync("openclaw", ["cron", "remove", String(dupId)], {
          stdio: ["ignore", "pipe", "pipe"],
          timeout: 15000,
        });
        removed.push(dupId);
      } catch (err) {
        console.error(
          `WARNING: failed to remove duplicate cron ${dupId} for ${name}: ${err.message}`,
        );
      }
    }
    return {
      name,
      action: removed.length ? "edited+deduped" : "edited",
      ids: [keepId],
      removed_duplicates: removed,
    };
  }

  const out = execFileSync(
    "openclaw",
    [
      "cron",
      "add",
      "--json",
      "--agent",
      agent.id,
      "--name",
      name,
      "--cron",
      job.schedule,
      "--tz",
      job.tz,
      "--session",
      "isolated",
      "--message",
      message,
      ...delivery.flags,
      "--timeout-seconds",
      String(job.timeout_seconds),
    ],
    { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 15000 },
  );
  let id = null;
  try {
    const parsed = JSON.parse(out || "{}");
    id = parsed.id || parsed.job_id || parsed.cron_id || null;
  } catch {}
  return { name, action: "added", ids: id ? [id] : [] };
}

function verifyOpenclawJobs(jobs, runKey, runDir) {
  const allJobs = listOpenclawJobs(true);
  const missing = [];
  for (const job of jobs) {
    const name = jobName(runKey, job.key);
    if (findExistingJobs(allJobs, name, runDir).length !== 1) missing.push(name);
  }
  return { ok: missing.length === 0, missing };
}

function installViaOpenclaw(runDir, envFile, runKey, jobs, delivery, agent) {
  const record = readJson(path.join(runDir, "cron-install.json"), {});
  const removed = reconcileOpenclawJobs(runDir, runKey, jobs, record);
  const installed = [];
  for (const job of jobs) {
    const result = openclawCronUpsert(job, runKey, runDir, delivery, agent, record);
    installed.push({
      key: job.key,
      name: result.name,
      action: result.action,
      ids: result.ids,
      schedule: job.schedule,
      tz: job.tz,
      schedule_basis: job.schedule_basis,
      timeout_seconds: job.timeout_seconds,
      command: job.command,
    });
  }
  const verification = verifyOpenclawJobs(jobs, runKey, runDir);
  if (!verification.ok) {
    throw new Error(
      `OpenClaw cron verification failed. Missing or duplicate run jobs after install: ${verification.missing.join(", ")}`,
    );
  }
  return { scheduler: "openclaw", agent, installed, removed, verification, delivery: publicDelivery(delivery) };
}

function publicDelivery(delivery) {
  if (!delivery) return undefined;
  const { flags, error, ...rest } = delivery;
  return { ...rest, openclaw_flags: flags || [] };
}

// Unix cron is opt-in: it writes only this run's marked block and preserves
// unrelated entries. Jobs use the current Node executable, not cron's PATH.
function readCrontab() {
  try {
    return execFileSync("crontab", ["-l"], { encoding: "utf8", timeout: 15000 });
  } catch (err) {
    if (err.status === 1 && /no crontab for/i.test(String(err.stderr))) return "";
    throw err;
  }
}

async function withCrontabLock(callback) {
  const lock = process.env.EGBE_CRON_LOCK_DIR || path.join("/tmp", `egbe-instantly-crontab-${process.geteuid()}.lock`);
  fs.mkdirSync(path.dirname(lock), {recursive:true, mode:0o700});
  try { fs.mkdirSync(lock, {mode:0o700}); }
  catch (err) {
    if (err.code !== "EEXIST") throw err;
    throw new Error(`Crontab installer lock exists: ${lock}. Retry after the installer ends; verify no installer is running before removing a stale lock.`);
  }
  try { return await callback(); }
  finally { fs.rmSync(lock, {recursive:true, force:true}); }
}

// A readable/writable crontab does not prove the daemon is executing jobs.
// Run a harmless, temporary Node probe through cron before claiming availability.
async function checkCronExecution(timeoutSeconds) {
  const marker = `EGBE-INSTANTLY-PROBE-${randomUUID()}`;
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "egbe-cron-probe-"));
  const script = path.join(directory, "probe.js");
  const proof = path.join(directory, "executed");
  fs.writeFileSync(script, `require("fs").writeFileSync(${JSON.stringify(proof)}, "executed");`, {mode:0o600});
  const command = [process.execPath, script].map(shellQuote).join(" ") + " >/dev/null 2>&1";
  if (/[\r\n]/.test(command)) {
    fs.rmSync(directory, {recursive:true, force:true});
    throw new Error("Cron probe paths must not contain newlines");
  }
  const entry = `* * * * * /bin/sh -c ${shellQuote(command)} # ${marker}`.replace(/%/g, "\\%");
  try {
    const prior = readCrontab();
    execFileSync("crontab", ["-"], {input:prior + (prior && !prior.endsWith("\n") ? "\n" : "") + entry + "\n", encoding:"utf8", timeout:15000});
    const deadline = Date.now() + timeoutSeconds * 1000;
    while (!fs.existsSync(proof) && Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    if (!fs.existsSync(proof)) throw new Error("Cron execution probe timed out: enable the cron daemon on an always-on host before launch");
    return {execution_verified:true};
  } finally {
    // Read again so unrelated edits made during the probe are preserved.
    try {
      const current = readCrontab();
      const updated = current.split("\n").filter(line => !line.includes(marker)).join("\n");
      execFileSync("crontab", ["-"], {input:updated, encoding:"utf8", timeout:15000});
      if (readCrontab().includes(marker)) throw new Error("Cron probe cleanup verification failed");
    } finally { fs.rmSync(directory, {recursive:true, force:true}); }
  }
}

function cronMarker(runDir) {
  return "EGBE-INSTANTLY-" + createHash("sha256").update(runDir).digest("hex").slice(0,24);
}

function recordedCronMarker(runDir) {
  const prior = readJson(path.join(runDir, "cron-install.json"), {});
  const marker = prior.marker || cronMarker(runDir);
  if (!/^EGBE-INSTANTLY-[0-9a-f]{24}$/.test(marker)) throw new Error("Invalid recorded cron marker");
  return marker;
}

function removeCronBlock(text, marker) {
  return text.replace(new RegExp(`^# BEGIN ${marker}\\n[\\s\\S]*?^# END ${marker}(?:\\n|$)`, "gm"), "");
}

async function removeScheduledJobs(runDir, runKey, scheduler) {
  if (scheduler === "cron") {
    if (!hasBinary("crontab")) throw new Error("crontab is unavailable; cannot verify removal");
    return withCrontabLock(() => {
      const marker = recordedCronMarker(runDir);
      const record = readJson(path.join(runDir, "cron-install.json"), {});
      const entries = (record.jobs || []).map((job) => job.entry).filter(Boolean);
      const remains = (text) => text.includes(marker) || entries.some((entry) => text.includes(entry));
      const updated = removeCronBlock(readCrontab(), marker);
      if (remains(updated)) throw new Error("Malformed cron block or recorded entries remain; repair before removal");
      execFileSync("crontab", ["-"], {input:updated, encoding:"utf8", timeout:15000});
      if (remains(readCrontab())) throw new Error("Cron removal verification failed");
    });
  }
  if (!hasBinary("openclaw")) throw new Error("openclaw is unavailable; cannot verify removal");
  const record = readJson(path.join(runDir, "cron-install.json"), {});
  const names = new Set((record.jobs || []).map((job) => job.name));
  const ids = new Set((record.jobs || []).flatMap((job) => job.ids || []).map(String));
  const matches = (job) => (names.has(job.name) || ids.has(String(job.id))) && jobTargetsRun(job, runDir);
  for (const key of ["reply", "monitor", "replenish", "conclude"]) names.add(jobName(runKey,key));
  const existing = listOpenclawJobs(true);
  if (existing.some(job => ids.has(String(job.id)) && !jobTargetsRun(job, runDir))) {
    throw new Error("Cannot verify recorded OpenClaw job scope; preserve the receipt and reconcile it before removal");
  }
  for (const job of existing) {
    if (matches(job)) execFileSync("openclaw", ["cron", "remove", String(job.id || job.name)], {timeout:15000, stdio:"pipe"});
  }
  if (listOpenclawJobs(true).some(matches)) throw new Error("OpenClaw removal verification failed");
}

async function installViaCron(runDir, envFile, runKey, jobs, timeoutSeconds) {
  return withCrontabLock(async () => {
  const marker = recordedCronMarker(runDir);
  const start = `# BEGIN ${marker}`;
  const end = `# END ${marker}`;
  const runner = path.join(__dirname, "run-cron-job.js");
  const installed = jobs.map((job) => {
    const command = [process.execPath, runner, "--job", job.key,
      "--run-dir", runDir, "--env-file", envFile,
      "--timeout-seconds", String(job.timeout_seconds)].map(shellQuote).join(" ")
      + ` >> ${shellQuote(path.join(runDir, `cron-${job.key}.log`))} 2>&1`;
    if (/[\r\n]/.test(command)) throw new Error("Cron paths must not contain newlines");
    // Cron interprets % even inside shell quotes. Force a POSIX shell regardless
    // of an existing user crontab's SHELL setting, then escape cron metacharacters.
    const entry = `${job.schedule} /bin/sh -c ${shellQuote(command)} # ${marker}:${job.key}`.replace(/%/g, "\\%");
    return {key:job.key, name:jobName(runKey, job.key), ids:[`${marker}:${job.key}`],
      schedule:job.schedule, tz:job.tz, schedule_basis:job.schedule_basis,
      timeout_seconds:job.timeout_seconds, command, entry};
  });
  const block = [start, ...installed.map((job) => job.entry), end].join("\n");
  const prior = readCrontab();
  const remaining = removeCronBlock(prior, marker);
  const receipt = readJson(path.join(runDir, "cron-install.json"), {});
  const recordedEntries = (receipt.jobs || []).map(job => job.entry).filter(Boolean);
  if (remaining.includes(marker) || recordedEntries.some(entry => remaining.includes(entry))) {
    throw new Error("Malformed run cron block or orphaned recorded entries; repair it before installing");
  }
  const execution = await checkCronExecution(timeoutSeconds);
  const afterProbe = removeCronBlock(readCrontab(), marker);
  if (afterProbe.includes(marker) || recordedEntries.some(entry => afterProbe.includes(entry))) {
    throw new Error("Run cron block changed during execution probe; repair orphaned entries before installing");
  }
  const updated = afterProbe + (afterProbe && !afterProbe.endsWith("\n") ? "\n" : "") + block + "\n";
  execFileSync("crontab", ["-"], {input:updated, encoding:"utf8", timeout:15000});
  const verified = readCrontab();
  if (!verified.split("\n").includes(start) || !verified.includes(block)) {
    throw new Error("Unix cron verification failed: run block missing after install");
  }
  return {scheduler:"cron", timezone:"host", marker, installed,
    verification:{ok:true, missing:[], ...execution}};
  });
}

// ---------------------------------------------------------------------------
// Manifest persistence
// ---------------------------------------------------------------------------

function persistCronJobsToManifest(runDir, result, manifest = readJson(path.join(runDir, "manifest.json"), null)) {
  const manifestPath = path.join(runDir, "manifest.json");
  if (!manifest) return;
  manifest.cron_jobs = {
    scheduler: result.scheduler,
    installed_at: isoNow(),
    jobs: (result.installed || []).map((j) => ({
      key: j.key,
      name: j.name,
      ids: j.ids || [],
      schedule: j.schedule,
      ...(j.tz ? { tz: j.tz } : {}),
    })),
  };
  writeJson(manifestPath, manifest);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv);
  const scheduler = args.scheduler || "openclaw";
  if (!["openclaw", "cron"].includes(scheduler)) throw new Error("Use --scheduler openclaw or cron");
  const timeoutSeconds = Number(args["scheduler-check-timeout-seconds"] || 75);
  if (!Number.isInteger(timeoutSeconds) || timeoutSeconds < 65 || timeoutSeconds > 120) {
    throw new Error("--scheduler-check-timeout-seconds must be an integer from 65 to 120 (cron needs a full minute plus startup margin)");
  }
  if (args["check-scheduler"]) {
    const binary = scheduler === "cron" ? "crontab" : "openclaw";
    if (!hasBinary(binary)) throw new Error(`${binary} is unavailable; choose a working scheduler before launch`);
    if (scheduler === "cron") await withCrontabLock(() => checkCronExecution(timeoutSeconds));
    else execFileSync("openclaw", ["cron", "list", "--json", "--all"], {timeout:15000, stdio:"pipe"});
    console.log(JSON.stringify({scheduler, available:true}));
    return;
  }
  const runDir = args["run-dir"] ? fs.realpathSync(path.resolve(args["run-dir"])) : null;
  if (!runDir) throw new Error("Missing --run-dir");

  // Cover receipts as well as scheduler writes: concurrent install/remove or
  // scheduler-switch requests for one run must not publish stale success.
  const runLock = path.join(runDir, ".scheduler-install.lock");
  try { fs.mkdirSync(runLock, {mode:0o700}); }
  catch (err) {
    if (err.code !== "EEXIST") throw err;
    throw new Error(`Run scheduler installer lock exists: ${runLock}. Verify no installer is running before removing a stale lock.`);
  }
  try {
  let manifest;
  try { manifest = readJson(path.join(runDir, "manifest.json")); }
  catch (err) {
    if (!args.remove) throw err;
    manifest = null; // Cleanup must remain available with a truncated manifest.
  }
  const prior = readJson(path.join(runDir, "cron-install.json"), {});
  const runKey = (args.remove ? prior.run_key || manifest?.run_key : manifest?.run_key) || path.basename(runDir);
  if (args.remove) {
    if (args["dry-run"]) { console.log(JSON.stringify({planned_removal:scheduler, run_dir:runDir})); return; }
    if (prior.installed && prior.scheduler !== scheduler) throw new Error("Select the recorded scheduler for removal");
    await removeScheduledJobs(runDir, runKey, scheduler);
    const result = {installed:false, scheduler, removed_at:isoNow(), jobs:[]};
    writeJson(path.join(runDir, "cron-install.json"), result);
    persistCronJobsToManifest(runDir, {scheduler, installed:[]}, manifest);
    console.log(JSON.stringify(result));
    return;
  }

  if (!manifest?.campaign?.id) throw new Error("Run manifest missing campaign ID");

  // Materialize OS creds from process.env into the run-scoped .env if needed.
  // Cron jobs run with their own environment and only see what's in --env-file,
  // so the run .env must contain OS_URL and OS_API_KEY.
  const envInit = ensureRunEnv(runDir, args["env-file"]);
  const envFile = fs.realpathSync(envInit.envFilePath);
  const stat = fs.statSync(envFile);
  if ((stat.mode & 0o077) !== 0) {
    // ensureRunEnv enforces 0o600; this is defense in depth.
    throw new Error(
      `Env file permissions are too open. Run: chmod 600 ${envFile}`,
    );
  }
  const env = readEnvFile(envFile);
  const os = getOsConfig(env);
  if (os.missing.length) {
    throw new Error(
      `Cannot install crons: ${os.missing.join(" and ")} not found in process.env or ${envFile}. ` +
        `This skill talks to Instantly through the OS outreach capability; it does NOT use a personal Instantly API key. ` +
        `Set OS_URL and OS_API_KEY at the container level, then re-run install-crons.js.`,
    );
  }

  const runSpec = readJson(path.join(runDir, "run-spec.json"), {});
  const sendWindow = sendWindowFor(runSpec, scheduler);
  const jobs = jobsForRun(runDir, envFile, runSpec, sendWindow, scheduler);
  const delivery = scheduler === "openclaw" ? resolveDelivery(args, runSpec) : null;
  const openclawAvailable = hasBinary("openclaw");
  const priorOpenclawAgent = prior?.installed === true && prior.scheduler === "openclaw" ? stringOption(prior.agent?.id) : null;

  if (args["dry-run"]) {
    const planned = scheduler === "cron" ? (hasBinary("crontab") ? "cron" : "none") : (openclawAvailable ? "openclaw" : "none");
    let agent;
    if (planned === "openclaw") {
      try { agent = resolveAgent(args, runDir, priorOpenclawAgent); } catch (err) { agent = { error: err.message }; }
    }
    console.log(
      JSON.stringify(
        {
          planned_scheduler: planned,
          run_key: runKey,
          run_dir: runDir,
          env_file: envFile,
          send_window: sendWindow,
          ...(agent ? { agent } : {}),
          ...(delivery ? { delivery: delivery.mode === "missing" ? { mode: "missing", error: delivery.error } : publicDelivery(delivery) } : {}),
          jobs: jobs.map((j) => ({
            key: j.key,
            name: jobName(runKey, j.key),
            schedule: j.schedule,
            tz: j.tz,
            command: j.command,
          })),
        },
        null,
        2,
      ),
    );
    return;
  }

  const priorInstall = readJson(path.join(runDir, "cron-install.json"), null);
  if (priorInstall?.installed === true && priorInstall.scheduler !== scheduler) {
    throw new Error("Run --remove with the recorded scheduler before switching schedulers; preserve the previous install record until removal verifies");
  }
  let result;
  if (scheduler === "cron") {
    if (!hasBinary("crontab")) throw new Error("crontab is unavailable; configure an always-on scheduler before launch");
    result = await installViaCron(runDir, envFile, runKey, jobs, timeoutSeconds);
  } else if (openclawAvailable) {
    // Fail before any scheduler write: a job without a route would run but
    // its reports and alerts would never reach anyone.
    if (delivery.mode === "missing") throw new Error(delivery.error);
    const agent = resolveAgent(args, runDir, priorOpenclawAgent);
    result = installViaOpenclaw(runDir, envFile, runKey, jobs, delivery, agent);
  } else {
    // The no-local-scheduler policy stands (non-zero exit so callers cannot
    // mistake manual mode for done), but a launched campaign still needs
    // monitoring — leave the operator a runbook: the exact commands and
    // cadence to run by hand until the OpenClaw scheduler is available.
    // All state lives under --run-dir, so a later install-crons.js rerun
    // picks up cleanly and overwrites this file.
    const manualJobs = jobs.map((j) => ({
      key: j.key,
      schedule: j.schedule,
      tz: j.tz,
      command: j.command,
    }));
    const cronInstallPath = path.join(runDir, "cron-install.json");
    const prior = readJson(cronInstallPath, null);
    if (prior?.installed === true) {
      // A successful install already exists — its jobs are likely still
      // firing. Do not clobber that record with installed:false just because
      // this shell lacks the CLI.
      throw new Error(
        "openclaw CLI unavailable in this shell, but cron-install.json already records a " +
          `successful install (scheduler: ${prior.scheduler}); jobs are likely still active. ` +
          "Leaving the record untouched — re-run install-crons.js from a shell with openclaw " +
          "on PATH to verify or update jobs.",
      );
    }
    writeJson(cronInstallPath, {
      installed: false,
      scheduler: "none",
      reason: "openclaw CLI unavailable",
      run_key: runKey,
      env_file: envFile,
      manual_monitoring: manualJobs,
      generated_at: isoNow(),
    });
    console.error(
      "OpenClaw cron is unavailable. Manual monitoring fallback — run these " +
        "by hand on the listed cadence, and re-run install-crons.js once the " +
        "scheduler is back:",
    );
    for (const job of manualJobs) {
      console.error(`  [${job.schedule} ${job.tz}] ${job.key}: ${job.command}`);
    }
    throw new Error(
      "OpenClaw cron is unavailable: install-crons.js requires the openclaw CLI. " +
        "Use --scheduler cron on an always-on host for direct script scheduling. " +
        "Manual commands were written to cron-install.json (manual_monitoring).",
    );
  }

  result.installed = result.installed || [];
  result.run_key = runKey;
  result.env_file = envFile;
  result.installed_at = isoNow();
  result.installed_status = true;

  writeJson(path.join(runDir, "cron-install.json"), {
    installed: true,
    installed_at: result.installed_at,
    scheduler: result.scheduler,
    env_file: envFile,
    run_key: runKey,
    jobs: result.installed,
    send_window: sendWindow,
    ...(result.agent ? { agent: result.agent } : {}),
    ...(result.delivery ? { delivery: result.delivery } : {}),
    ...(result.marker ? { marker: result.marker } : {}),
    ...(result.verification ? { verification: result.verification } : {}),
  });

  persistCronJobsToManifest(runDir, result);

  console.log(JSON.stringify(result, null, 2));
  } finally { fs.rmSync(runLock, {recursive:true, force:true}); }
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exit(1);
});
