const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { DatabaseSync } = require('node:sqlite');
const store = require('./outreach-db');

test('a Git clone carries committed outreach records without WAL or credentials', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'egbe-outreach-handoff-'));
  const source = path.join(root, 'source');
  const channel = 'egbe-docs/marketing/campaigns/instantly';
  const run = path.join(source, channel, 'synthetic');
  fs.mkdirSync(run, { recursive: true });
  const dbPath = store.initDb(run);
  assert.equal(dbPath, path.join(source, channel, 'outreach.db'));
  // Keep the writer open during the copy: normal process exit must not be
  // responsible for moving committed data from a WAL into the main file.
  const db = new DatabaseSync(dbPath);
  try {
    assert.equal(db.prepare('PRAGMA journal_mode').get().journal_mode, 'delete');
    db.exec("INSERT INTO outreach_runs(run_key, product_name, segment_name, offer_headline, created_at, updated_at) VALUES ('synthetic', 'Test', 'Test', 'Test', '2026-01-01', '2026-01-01')");
    db.exec("INSERT INTO leads(email, source, created_at, updated_at) VALUES ('contact@example.invalid', 'fixture', '2026-01-01', '2026-01-01')");
    db.exec("INSERT INTO reply_queue(run_key, email, message_id, intent, recommended_reply, created_at, updated_at) VALUES ('synthetic', 'contact@example.invalid', 'reply-1', 'question', 'Synthetic reply', '2026-01-01', '2026-01-01')");
    fs.writeFileSync(path.join(run, '.env'), 'OS_API_KEY=synthetic-only\n');
    fs.writeFileSync(path.join(run, 'manifest.json'), '{"campaign_id":"synthetic"}\n');
    fs.writeFileSync(path.join(run, '.scheduler-install.lock'), 'synthetic\n');
    fs.writeFileSync(path.join(source, '.gitignore'), '*.db\n');
    execFileSync('python3', [path.resolve(__dirname, '../../../quickstart/scripts/prepare-artifacts.py'), '--project-root', source]);
    const git = (...args) => execFileSync('git', ['-C', source, ...args], { stdio: 'pipe' });
    git('init');
    git('add', '.');
    git('-c', 'user.name=Artifact test', '-c', 'user.email=artifact-test@example.invalid',
        '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Synthetic handoff');
    const clone = path.join(root, 'clone');
    execFileSync('git', ['clone', '--no-hardlinks', source, clone], { stdio: 'pipe' });
    const copy = new DatabaseSync(path.join(clone, channel, 'outreach.db'), { readOnly: true });
    try {
      assert.equal(copy.prepare('SELECT COUNT(*) AS count FROM leads').get().count, 1);
      assert.equal(copy.prepare('SELECT recommended_reply FROM reply_queue').get().recommended_reply, 'Synthetic reply');
    } finally { copy.close(); }
    assert(fs.existsSync(path.join(clone, channel, 'synthetic/manifest.json')));
    assert(!fs.existsSync(path.join(clone, channel, 'synthetic/.env')));
    assert(!fs.existsSync(path.join(clone, channel, 'synthetic/.scheduler-install.lock')));
    assert(!fs.existsSync(dbPath + '-wal'));
  } finally {
    db.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
});
