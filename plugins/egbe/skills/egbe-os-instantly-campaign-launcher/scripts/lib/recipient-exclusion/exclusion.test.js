const test = require('node:test');
const assert = require('node:assert/strict');
const { listLeadRows, assessRecipient, assessCampaignOptOuts } = require('./index');
const { InstantlyClient } = require('../instantly-client');

const lead = (id, email = 'stop@example.test', campaign = 'campaign-a', extra = {}) => ({ id, email, campaign, status: 1, ...extra });
function evidence(id, extra = {}) {
  return { status: 200, body: { campaign_id: 'campaign-a', lead_id: id, state: 'confirmed',
    scope: 'main_campaign_sequence', lead_status: 3, interest_status: -1,
    observed_at: '2026-11-12T12:00:00Z', ...extra } };
}
function fixture(rows) {
  const writes = [];
  return { writes, listLeads: async () => ({ status: 200, body: { items: rows } }),
    getRecipientExclusion: async (c, id) => evidence(id),
    excludeRecipient: async (c, id) => { writes.push([c, id]); return evidence(id); } };
}

test('native short page with continuation must not hide a later eligible refusal', async () => {
  const pages = [];
  const client = fixture([]);
  client.listLeads = async (c, { starting_after }) => {
    pages.push(starting_after);
    return { status: 200, body: !starting_after ? { items: [lead('first', 'other@example.test')], next_starting_after: 'next' }
      : starting_after === 'next' ? { items: [lead('refusal')], next_starting_after: 'end' } : { items: [] } };
  };
  client.getRecipientExclusion = async (c, id) => evidence(id, { state: 'eligible', lead_status: 1, interest_status: null });
  const result = await assessCampaignOptOuts(client, 'campaign-a', new Set(['stop@example.test']));
  assert.equal(result.ok, false);
  assert.deepEqual(pages, [undefined, 'next', 'end']);
  assert.equal(result.recipients[0].evidence[0].lead_id, 'refusal');
  assert.deepEqual(client.writes, []);
});

test('126 retained rows allow exclusion only with fresh owned evidence; no activation or deletion', async () => {
  const rows = Array.from({ length: 126 }, (_, i) => lead(`id-${i}`, i === 125 ? 'stop@example.test' : `other-${i}@example.test`));
  const client = fixture(rows);
  client.listLeads = async (c, { starting_after }) => ({ status: 200, body: {
    items: starting_after ? rows.slice(100) : rows.slice(0, 100),
    next_starting_after: starting_after ? null : 'page-2',
  } });
  const result = await assessCampaignOptOuts(client, 'campaign-a', new Set(['stop@example.test']));
  assert.equal(result.ok, true);
  assert.equal(result.recipients[0].state, 'excluded');
  assert.equal(rows.length, 126);
  assert.deepEqual(client.writes, []);
});

for (const [name, rows, cursor] of [
  ['duplicate ID', [lead('a'), lead('a')]],
  ['foreign campaign', [lead('a', 'stop@example.test', 'foreign')]],
  ['missing campaign', [{ id: 'a', email: 'stop@example.test' }]],
  ['missing ID', [{ campaign: 'campaign-a', email: 'stop@example.test' }]],
  ['empty email', [lead('a', '')]],
  ['empty page with continuation', [], 'next'],
  ['malformed cursor', [lead('a')], {}],
]) test(`${name} remains unknown, never absence/excluded`, async () => {
  const client = fixture(rows);
  client.listLeads = async () => ({ status: 200, body: { items: rows, next_starting_after: cursor } });
  const result = await assessRecipient(client, 'campaign-a', 'stop@example.test', { confirmed: true, mutate: true });
  assert.equal(result.state, 'unknown');
  assert.deepEqual(client.writes, []);
});

test('ignored/repeated cursor and read outage remain incomplete', async () => {
  const client = fixture([]);
  let n = 0;
  client.listLeads = async () => ({ status: 200, body: { items: [lead(`a-${n++}`)], next_starting_after: 'same' } });
  assert.equal((await listLeadRows(client, 'campaign-a')).ok, false);
  client.listLeads = async () => { throw new Error('timeout'); };
  assert.equal((await listLeadRows(client, 'campaign-a')).ok, false);
});

test('local confirmation is mandatory, provider state alone grants no exception', async () => {
  const client = fixture([lead('a')]);
  assert.equal((await assessRecipient(client, 'campaign-a', 'stop@example.test')).state, 'unknown');
  assert.deepEqual(client.writes, []);
});

test('every same-email copy needs independently matching scope, status and identity', async () => {
  const client = fixture([lead('a'), lead('b')]);
  for (const extra of [{ campaign_id: 'foreign' }, { lead_id: 'other' }, { state: 'unsupported' },
    { state: 'unknown' }, { state: 'confirmed', lead_status: 1 }, { interest_status: 0 },
    { scope: 'whole_campaign' }, { observed_at: null }]) {
    client.getRecipientExclusion = async (c, id) => evidence(id, id === 'b' ? extra : {});
    assert.equal((await assessRecipient(client, 'campaign-a', 'stop@example.test', { confirmed: true })).state, 'unknown');
  }
});

test('timeout after commit is recovered by GET, never repeated POST', async () => {
  const client = fixture([lead('a')]);
  let committed = false;
  client.getRecipientExclusion = async () => evidence('a', committed ? {} : { state: 'eligible', lead_status: 1 });
  client.excludeRecipient = async (c, id) => { client.writes.push([c, id]); committed = true; throw new Error('timeout'); };
  assert.equal((await assessRecipient(client, 'campaign-a', 'stop@example.test', { confirmed: true, mutate: true })).state, 'excluded');
  assert.deepEqual(client.writes, [['campaign-a', 'a']]);
  await assessRecipient(client, 'campaign-a', 'stop@example.test', { confirmed: true, mutate: true });
  assert.equal(client.writes.length, 1);
});

test('mixed old server or rejected/unknown read never falls back to a mutation', async () => {
  const client = fixture([lead('a')]);
  for (const response of [{ status: 404 }, { status: 503 }, evidence('a', { state: 'unsupported' }), evidence('a', { state: 'unknown' })]) {
    client.getRecipientExclusion = async () => response;
    assert.equal((await assessRecipient(client, 'campaign-a', 'stop@example.test', { confirmed: true, mutate: true })).state, 'unknown');
  }
  assert.deepEqual(client.writes, []);
});

test('client preserves membership API and uses fixed semantic body with no write retry', async () => {
  const client = new InstantlyClient({ osApiKey: 'test', osUrl: 'http://example.test' });
  const calls = [];
  client.request = async (...args) => { calls.push(args); return { status: 200, body: { items: [lead('a')] } }; };
  const members = await client.listLeadEmails('campaign-a');
  assert.equal(members.ok, true);
  assert.deepEqual([...members.emails], ['stop@example.test']);
  await client.excludeRecipient('campaign-a', 'a');
  const call = calls.at(-1);
  assert.deepEqual(call, ['POST', '/campaigns/campaign-a/leads/a/exclusion', { intent: 'confirmed_opt_out' }, null, 0, { retryOn: [] }]);
});
