const path = require("path");
const { DatabaseSync } = require("node:sqlite");
const { ensureDir, isoNow, normalizeEmail } = require("./helpers");

function dbPathForRun(runDir) {
  // runDir = egbe-docs/marketing/campaigns/instantly/<id>
  return path.resolve(runDir, "..", "outreach.db");
}

const _dbCache = new Map();

function openDb(dbPath) {
  let db = _dbCache.get(dbPath);
  if (db) return db;
  ensureDir(path.dirname(dbPath));
  db = new DatabaseSync(dbPath);
  // Committed campaign state must be portable in the tracked database file,
  // not split between it and an untracked WAL. Quiesce workers before Git sync.
  db.exec("PRAGMA journal_mode=DELETE;");
  db.exec("PRAGMA foreign_keys=ON;");
  db.exec("PRAGMA busy_timeout=5000;");
  _dbCache.set(dbPath, db);
  return db;
}

function columnExists(db, table, column) {
  try {
    const rows = db.prepare(`PRAGMA table_info(${table});`).all();
    return rows.some((r) => r.name === column);
  } catch (_) {
    return false;
  }
}

function ensureColumn(db, table, column, definition) {
  if (columnExists(db, table, column)) return;
  try {
    db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${definition};`);
  } catch (_) {
    // ignore: race or already-added
  }
}

function initDb(runDir) {
  const dbPath = dbPathForRun(runDir);
  const db = openDb(dbPath);

  db.exec(`
    CREATE TABLE IF NOT EXISTS outreach_runs (
      run_key TEXT PRIMARY KEY,
      product_name TEXT NOT NULL,
      segment_name TEXT NOT NULL,
      offer_headline TEXT NOT NULL,
      campaign_id TEXT,
      campaign_name TEXT,
      status TEXT NOT NULL DEFAULT 'draft',
      verdict TEXT,
      verdict_reason TEXT,
      reply_rate REAL,
      concluded_at TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS leads (
      email TEXT PRIMARY KEY,
      first_name TEXT,
      last_name TEXT,
      company_name TEXT,
      website TEXT,
      title TEXT,
      linkedin_url TEXT,
      city TEXT,
      state TEXT,
      country TEXT,
      source TEXT NOT NULL,
      source_ref TEXT,
      email_status TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS run_leads (
      run_key TEXT NOT NULL,
      email TEXT NOT NULL,
      campaign_id TEXT,
      imported_at TEXT,
      verification_status TEXT NOT NULL DEFAULT 'pending',
      last_known_status TEXT NOT NULL DEFAULT 'new',
      last_contacted_at TEXT,
      last_replied_at TEXT,
      last_bounced_at TEXT,
      last_unsubscribed_at TEXT,
      reply_intent TEXT,
      ownership_tag TEXT,
      notes TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY (run_key, email),
      FOREIGN KEY (run_key) REFERENCES outreach_runs(run_key),
      FOREIGN KEY (email) REFERENCES leads(email)
    );

    CREATE TABLE IF NOT EXISTS lead_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_key TEXT NOT NULL,
      email TEXT NOT NULL,
      event_type TEXT NOT NULL,
      event_at TEXT NOT NULL,
      payload_json TEXT,
      FOREIGN KEY (run_key) REFERENCES outreach_runs(run_key),
      FOREIGN KEY (email) REFERENCES leads(email)
    );

    CREATE TABLE IF NOT EXISTS reply_queue (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_key TEXT NOT NULL,
      email TEXT NOT NULL,
      message_id TEXT,
      intent TEXT NOT NULL,
      recommended_reply TEXT,
      status TEXT NOT NULL DEFAULT 'pending',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (run_key) REFERENCES outreach_runs(run_key),
      FOREIGN KEY (email) REFERENCES leads(email)
    );

    CREATE INDEX IF NOT EXISTS idx_run_leads_campaign_id ON run_leads(campaign_id);
    CREATE INDEX IF NOT EXISTS idx_run_leads_status ON run_leads(last_known_status);
    CREATE INDEX IF NOT EXISTS idx_lead_events_run_key ON lead_events(run_key);
    CREATE INDEX IF NOT EXISTS idx_lead_events_email ON lead_events(email);
    CREATE INDEX IF NOT EXISTS idx_reply_queue_status ON reply_queue(status);

    CREATE UNIQUE INDEX IF NOT EXISTS idx_confirmed_opt_out_message
      ON lead_events(run_key, email, json_extract(payload_json, '$.message_id'))
      WHERE event_type = 'opt_out_confirmed';
    -- A run's report/reply rebuild must not erase project-wide refusals.
    -- Foreign keys also retain the referenced run and recipient records.
    CREATE TRIGGER IF NOT EXISTS preserve_confirmed_opt_out
      BEFORE DELETE ON lead_events WHEN OLD.event_type = 'opt_out_confirmed'
      BEGIN SELECT RAISE(IGNORE); END;
  `);

  // Backfill columns added after the original schema.
  ensureColumn(db, "outreach_runs", "verdict", "TEXT");
  ensureColumn(db, "outreach_runs", "verdict_reason", "TEXT");
  ensureColumn(db, "outreach_runs", "reply_rate", "REAL");
  ensureColumn(db, "outreach_runs", "concluded_at", "TEXT");
  db.exec(
    `CREATE INDEX IF NOT EXISTS idx_outreach_runs_product_concluded
       ON outreach_runs(product_name, concluded_at);`,
  );

  return dbPath;
}

function upsertRun(dbPath, run) {
  const db = openDb(dbPath);
  const now = isoNow();
  db.prepare(
    `INSERT INTO outreach_runs (
       run_key, product_name, segment_name, offer_headline,
       campaign_id, campaign_name, status, created_at, updated_at
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(run_key) DO UPDATE SET
       product_name = excluded.product_name,
       segment_name = excluded.segment_name,
       offer_headline = excluded.offer_headline,
       campaign_id = excluded.campaign_id,
       campaign_name = excluded.campaign_name,
       status = excluded.status,
       updated_at = excluded.updated_at;`,
  ).run(
    run.run_key,
    run.product_name || "Unknown product",
    run.segment_name || "Unknown segment",
    run.offer_headline || "Unknown offer",
    run.campaign_id ?? null,
    run.campaign_name ?? null,
    run.status || "draft",
    run.created_at || now,
    now,
  );
}

function inferLeadSource(lead) {
  if (lead.source) return lead.source;
  if (lead.apollo_id) return "apollo";
  return "import";
}

function inferLeadSourceRef(lead) {
  return lead.source_ref || lead.apollo_id || null;
}

function upsertLead(dbPath, lead) {
  const email = normalizeEmail(lead.email);
  if (!email) return;
  const db = openDb(dbPath);
  const now = isoNow();
  db.prepare(
    `INSERT INTO leads (
       email, first_name, last_name, company_name, website,
       title, linkedin_url, city, state, country,
       source, source_ref, email_status, created_at, updated_at
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(email) DO UPDATE SET
       first_name = COALESCE(excluded.first_name, leads.first_name),
       last_name = COALESCE(excluded.last_name, leads.last_name),
       company_name = COALESCE(excluded.company_name, leads.company_name),
       website = COALESCE(excluded.website, leads.website),
       title = COALESCE(excluded.title, leads.title),
       linkedin_url = COALESCE(excluded.linkedin_url, leads.linkedin_url),
       city = COALESCE(excluded.city, leads.city),
       state = COALESCE(excluded.state, leads.state),
       country = COALESCE(excluded.country, leads.country),
       source = COALESCE(excluded.source, leads.source),
       source_ref = COALESCE(excluded.source_ref, leads.source_ref),
       email_status = COALESCE(excluded.email_status, leads.email_status),
       updated_at = excluded.updated_at;`,
  ).run(
    email,
    lead.first_name || lead.firstName || null,
    lead.last_name || lead.lastName || null,
    lead.company_name || lead.companyName || null,
    lead.website || null,
    lead.title || null,
    lead.linkedin_url || lead.linkedinUrl || null,
    lead.city || null,
    lead.state || null,
    lead.country || null,
    inferLeadSource(lead),
    inferLeadSourceRef(lead),
    lead.email_status || null,
    now,
    now,
  );
}

function upsertRunLead(dbPath, entry) {
  const email = normalizeEmail(entry.email);
  if (!entry.run_key || !email) return;
  const db = openDb(dbPath);
  const now = isoNow();
  db.prepare(
    `INSERT INTO run_leads (
       run_key, email, campaign_id, imported_at, verification_status,
       last_known_status, last_contacted_at, last_replied_at, last_bounced_at,
       last_unsubscribed_at, reply_intent, ownership_tag, notes, created_at, updated_at
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(run_key, email) DO UPDATE SET
       campaign_id = COALESCE(excluded.campaign_id, run_leads.campaign_id),
       imported_at = COALESCE(excluded.imported_at, run_leads.imported_at),
       verification_status = COALESCE(excluded.verification_status, run_leads.verification_status),
       last_known_status = COALESCE(excluded.last_known_status, run_leads.last_known_status),
       last_contacted_at = COALESCE(excluded.last_contacted_at, run_leads.last_contacted_at),
       last_replied_at = COALESCE(excluded.last_replied_at, run_leads.last_replied_at),
       last_bounced_at = COALESCE(excluded.last_bounced_at, run_leads.last_bounced_at),
       last_unsubscribed_at = COALESCE(excluded.last_unsubscribed_at, run_leads.last_unsubscribed_at),
       reply_intent = COALESCE(excluded.reply_intent, run_leads.reply_intent),
       ownership_tag = COALESCE(excluded.ownership_tag, run_leads.ownership_tag),
       notes = COALESCE(excluded.notes, run_leads.notes),
       updated_at = excluded.updated_at;`,
  ).run(
    entry.run_key,
    email,
    entry.campaign_id || null,
    entry.imported_at || null,
    entry.verification_status || "pending",
    entry.last_known_status || "new",
    entry.last_contacted_at || null,
    entry.last_replied_at || null,
    entry.last_bounced_at || null,
    entry.last_unsubscribed_at || null,
    entry.reply_intent || null,
    entry.ownership_tag || null,
    entry.notes || null,
    now,
    now,
  );
}

function insertLeadEvent(dbPath, event) {
  const email = normalizeEmail(event.email);
  if (!event.run_key || !email || !event.event_type) return;
  const db = openDb(dbPath);
  db.prepare(
    `INSERT INTO lead_events (run_key, email, event_type, event_at, payload_json)
     VALUES (?, ?, ?, ?, ?);`,
  ).run(
    event.run_key,
    email,
    event.event_type,
    event.event_at || isoNow(),
    event.payload_json ? JSON.stringify(event.payload_json) : null,
  );
}

function confirmOptOut(dbPath, { run_key, email, message_id, campaign_id, event_at }) {
  email = normalizeEmail(email);
  if (!run_key || !email || !message_id || !campaign_id)
    throw new Error("Confirmed opt-out requires run, campaign recipient and source message ID");
  const db = openDb(dbPath);
  const result = db.prepare(
    `INSERT OR IGNORE INTO lead_events (run_key, email, event_type, event_at, payload_json)
     VALUES (?, ?, 'opt_out_confirmed', ?, ?);`,
  ).run(run_key, email, event_at || isoNow(), JSON.stringify({ message_id, campaign_id }));
  return { inserted: result.changes === 1, email, message_id };
}

function upsertReplyQueueItem(dbPath, item) {
  const email = normalizeEmail(item.email);
  if (!item.run_key || !email || !item.intent) return;
  const db = openDb(dbPath);
  const now = isoNow();
  db.prepare(
    `INSERT INTO reply_queue (
       run_key, email, message_id, intent, recommended_reply,
       status, created_at, updated_at
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);`,
  ).run(
    item.run_key,
    email,
    item.message_id || null,
    item.intent,
    item.recommended_reply || null,
    item.status || "pending",
    now,
    now,
  );
}

function setReplyQueueStatus(dbPath, { run_key, message_id, status }) {
  if (!run_key || !message_id || !status) return;
  const db = openDb(dbPath);
  db.prepare(
    `UPDATE reply_queue SET status = ?, updated_at = ?
     WHERE run_key = ? AND message_id = ?;`,
  ).run(status, isoNow(), run_key, message_id);
}

function queryAll(dbPath, sql, params = []) {
  const db = openDb(dbPath);
  return db.prepare(sql).all(...params);
}

function queryAllReadOnly(dbPath, sql, params = []) {
  const db = new DatabaseSync(dbPath, { readOnly: true });
  try {
    db.exec("PRAGMA busy_timeout=5000;");
    return db.prepare(sql).all(...params);
  } finally {
    db.close();
  }
}

module.exports = {
  dbPathForRun,
  initDb,
  upsertRun,
  upsertLead,
  upsertRunLead,
  insertLeadEvent,
  confirmOptOut,
  upsertReplyQueueItem,
  setReplyQueueStatus,
  queryAll,
  queryAllReadOnly,
};
