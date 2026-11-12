#!/usr/bin/env node
const path = require("path");
const { parseArgs } = require("./lib/helpers");
const { dbPathForRun, queryAllReadOnly } = require("./lib/outreach-db");

function fail(message) {
  console.error(message);
  process.exit(1);
}

function runQuery(dbPath, sql, params = []) {
  return queryAllReadOnly(dbPath, sql, params);
}

function runKeyFilter(runKey, alias) {
  if (!runKey) return { clause: "", params: [] };
  return { clause: `WHERE ${alias}.run_key = ?`, params: [runKey] };
}

function main() {
  const args = parseArgs(process.argv);
  const runDir = args["run-dir"] ? path.resolve(args["run-dir"]) : null;
  const dbPath = args["db"]
    ? path.resolve(args["db"])
    : runDir
      ? dbPathForRun(runDir)
      : null;
  const mode = String(args.mode || "summary").trim();
  const limit = Math.max(1, Number(args.limit || 20));
  const runKey = args["run-key"] ? String(args["run-key"]) : null;

  if (!dbPath) fail("Missing --run-dir or --db");

  let sql;
  let params = [];
  if (mode === "summary") {
    const rkf = runKeyFilter(runKey, "r");
    // Attribute a confirmed refusal to its source run, not every campaign
    // containing the recipient. UNION preserves old provider/status evidence
    // without double-counting multiple confirmations or relying on mutable status.
    sql = `
      WITH unsubscribed AS (
        SELECT run_key, email FROM run_leads WHERE last_known_status = 'unsubscribed'
        UNION
        SELECT run_key, email FROM lead_events WHERE event_type = 'opt_out_confirmed'
      )
      SELECT
        r.run_key,
        r.product_name,
        r.segment_name,
        r.offer_headline,
        r.campaign_id,
        r.campaign_name,
        r.status,
        r.updated_at,
        COUNT(rl.email) AS leads_total,
        SUM(CASE WHEN rl.last_known_status = 'imported' THEN 1 ELSE 0 END) AS leads_imported,
        SUM(CASE WHEN rl.last_known_status = 'replied' THEN 1 ELSE 0 END) AS leads_replied,
        SUM(CASE WHEN rl.last_known_status = 'bounced' THEN 1 ELSE 0 END) AS leads_bounced,
        (SELECT COUNT(*) FROM unsubscribed u WHERE u.run_key = r.run_key) AS leads_unsubscribed
      FROM outreach_runs r
      LEFT JOIN run_leads rl ON rl.run_key = r.run_key
      ${rkf.clause}
      GROUP BY r.run_key
      ORDER BY r.updated_at DESC
      LIMIT ?;
    `;
    params = [...rkf.params, limit];
  } else if (mode === "leads") {
    const rkf = runKeyFilter(runKey, "rl");
    // Suppression applies across this project's runs. Expose it separately from
    // last_known_status: a local refusal does not prove provider sends stopped.
    sql = `
      WITH confirmed_refusals AS (
        SELECT email, MIN(event_at) AS confirmed_at
        FROM lead_events WHERE event_type = 'opt_out_confirmed'
        GROUP BY email
      )
      SELECT
        rl.run_key,
        rl.email,
        l.first_name,
        l.last_name,
        l.company_name,
        l.title,
        l.email_status,
        rl.verification_status,
        rl.last_known_status,
        CASE WHEN refusal.email IS NOT NULL THEN 1 ELSE 0 END AS opt_out_confirmed,
        refusal.confirmed_at AS opt_out_confirmed_at,
        rl.reply_intent,
        rl.imported_at,
        rl.last_replied_at,
        rl.updated_at
      FROM run_leads rl
      LEFT JOIN leads l ON l.email = rl.email
      LEFT JOIN confirmed_refusals refusal ON refusal.email = rl.email
      ${rkf.clause}
      ORDER BY rl.updated_at DESC
      LIMIT ?;
    `;
    params = [...rkf.params, limit];
  } else if (mode === "queue") {
    sql = `
      SELECT
        id,
        run_key,
        email,
        message_id,
        intent,
        status,
        recommended_reply,
        updated_at
      FROM reply_queue
      ${runKey ? "WHERE run_key = ?" : ""}
      ORDER BY updated_at DESC
      LIMIT ?;
    `;
    params = runKey ? [runKey, limit] : [limit];
  } else if (mode === "events") {
    sql = `
      SELECT
        id,
        run_key,
        email,
        event_type,
        event_at,
        payload_json
      FROM lead_events
      ${runKey ? "WHERE run_key = ?" : ""}
      ORDER BY event_at DESC, id DESC
      LIMIT ?;
    `;
    params = runKey ? [runKey, limit] : [limit];
  } else {
    fail(
      `Unsupported --mode: ${mode}. Expected one of: summary, leads, queue, events`,
    );
  }

  const rows = runQuery(dbPath, sql, params);
  process.stdout.write(`${JSON.stringify(rows, null, 2)}\n`);
}

main();
