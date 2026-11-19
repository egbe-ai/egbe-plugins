const validId = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(value);
const successful = response => response?.status >= 200 && response.status < 300;

async function listLeadRows(client, campaignId) {
  const rows = [];
  const ids = new Set();
  const cursors = new Set();
  let cursor;
  for (let page = 0; page < 1000; page++) {
    let response;
    try { response = await client.listLeads(campaignId, { limit: 100, starting_after: cursor }); }
    catch { return { ok: false, rows }; }
    if (!successful(response)) return { ok: false, rows };
    const body = response.body;
    const items = Array.isArray(body) ? body : body?.items;
    if (!Array.isArray(items)) return { ok: false, rows };
    for (const row of items) {
      if (!validId(row?.id) || ids.has(row.id)
        || row.campaign !== campaignId
        || (Object.hasOwn(row, 'campaign_id') && row.campaign_id !== campaignId)
        || typeof row.email !== 'string' || !row.email.trim()) return { ok: false, rows };
      ids.add(row.id);
      rows.push(row);
    }
    // Native continuation is authoritative even on short pages. Legacy array
    // and older gateway responses use last-ID pagination on full pages only.
    const declared = !Array.isArray(body) && Object.hasOwn(body, 'next_starting_after');
    const next = declared ? body.next_starting_after : (items.length >= 100 ? items.at(-1)?.id : null);
    if (next == null || next === '') return { ok: true, rows };
    if (!items.length || typeof next !== 'string' || !next.trim() || next.length > 512
      || cursors.has(next)) return { ok: false, rows };
    cursors.add(next);
    cursor = next;
  }
  return { ok: false, rows };
}

function confirmedEvidence(response, campaignId, leadId) {
  const body = response?.body;
  return successful(response) && body?.state === 'confirmed'
    && body.campaign_id === campaignId && body.lead_id === leadId
    && body.scope === 'main_campaign_sequence'
    && body.lead_status === 3 && body.interest_status === -1
    && typeof body.observed_at === 'string' && Number.isFinite(Date.parse(body.observed_at));
}

// Caller supplies persisted refusal authority; native labels cannot create it.
// Every matching retained copy needs its own fresh, owned semantic readback.
async function assessRecipient(client, campaignId, email, { confirmed = false, mutate = false, population = null } = {}) {
  if (!confirmed) return { state: 'unknown', reason: 'local_refusal_unconfirmed' };
  const members = population || await listLeadRows(client, campaignId);
  if (!members.ok) return { state: 'unknown', reason: 'membership_unavailable' };
  const matching = members.rows.filter(row => row.email.trim().toLowerCase() === email.trim().toLowerCase());
  if (!matching.length) return { state: 'absent', evidence: [] };
  const evidence = [];
  for (const lead of matching) {
    let response;
    try {
      response = await client.getRecipientExclusion(campaignId, lead.id);
      // Once an uncertain write occurred, GET is the only automatic recovery.
      if (!confirmedEvidence(response, campaignId, lead.id) && mutate && successful(response)
        && response.body?.state === 'eligible'
        && response.body.campaign_id === campaignId && response.body.lead_id === lead.id
        && response.body.scope === 'main_campaign_sequence') {
        try { response = await client.excludeRecipient(campaignId, lead.id); }
        catch { response = null; }
        if (!confirmedEvidence(response, campaignId, lead.id))
          response = await client.getRecipientExclusion(campaignId, lead.id);
      }
    } catch { response = null; }
    evidence.push({ lead_id: lead.id, confirmed: confirmedEvidence(response, campaignId, lead.id),
      result: successful(response) ? response.body : null });
  }
  return { state: evidence.every(item => item.confirmed) ? 'excluded' : 'unknown', evidence };
}

async function assessCampaignOptOuts(client, campaignId, emails) {
  const population = await listLeadRows(client, campaignId);
  if (!population.ok) return { ok: false, reason: 'campaign_membership_unavailable', recipients: [] };
  const recipients = [];
  for (const email of emails) recipients.push({ email,
    ...await assessRecipient(client, campaignId, email, { confirmed: true, population }) });
  return { ok: recipients.every(row => ['absent', 'excluded'].includes(row.state)), recipients };
}

module.exports = { listLeadRows, assessRecipient, assessCampaignOptOuts, confirmedEvidence };
