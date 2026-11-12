const { listLeadRows } = require('./recipient-exclusion');
const connectionHeaders = require('./connection-identity');
const http = require('http');
const https = require('https');
const { URL } = require('url');

const RETRY_DEFAULT = [408, 425, 429, 500, 502, 503, 504];
// Rate limited: the request was refused before any work was done.
const RETRY_NOT_PROCESSED = [429];
// 1,000 pages of 100 leads; far above any campaign this skill runs.
const MAX_LEAD_PAGES = 1000;

class InstantlyClient {
  constructor({ osApiKey, osUrl, connectionEnvFile = null, timeoutMs = 30000, verbose = false }) {
    if (!osApiKey) throw new Error('Missing OS_API_KEY');
    if (!osUrl) throw new Error('Missing OS_URL');
    this.osApiKey = osApiKey;
    this.baseUrl = `${osUrl.replace(/\/$/, '')}/outreach/instantly`;
    this.identityHeaders = connectionHeaders(osUrl, connectionEnvFile);
    this.timeoutMs = timeoutMs;
    this.verbose = verbose;
  }

  // retryOn: statuses worth repeating. The default is for reads and writes
  // that end in the same state when repeated; calls that create something
  // (campaign, leads, tag, reply) pass only statuses that prove nothing was
  // processed.
  async request(method, pathname, body = null, query = null, attempt = 0, { retryOn = RETRY_DEFAULT } = {}) {
    const url = new URL(String(pathname || '').replace(/^\/+/, ''), `${this.baseUrl}/`);
    if (query) {
      for (const [key, value] of Object.entries(query)) {
        if (Array.isArray(value)) value.forEach(v => v != null && url.searchParams.append(key, String(v)));
        else if (value != null) url.searchParams.set(key, String(value));
      }
    }

    const payload = body == null ? null : JSON.stringify(body);
    const transport = url.protocol === 'https:' ? https : (url.protocol === 'http:' ? http : null);
    if (!transport) throw new Error(`Unsupported protocol for OS_URL: ${url.protocol}`);
    const options = {
      method,
      hostname: url.hostname,
      port: url.port || undefined,
      path: url.pathname + url.search,
      headers: {
        ...(url.origin === new URL(this.baseUrl).origin ? this.identityHeaders : {}),
        Authorization: `Bearer ${this.osApiKey}`,
        Accept: 'application/json',
      },
      timeout: this.timeoutMs,
    };
    if (payload) {
      options.headers['Content-Type'] = 'application/json';
      options.headers['Content-Length'] = Buffer.byteLength(payload);
    }

    const response = await new Promise((resolve, reject) => {
      const req = transport.request(options, (res) => {
        let data = '';
        res.on('data', c => data += c);
        res.on('end', () => {
          let parsed = data;
          try { parsed = data ? JSON.parse(data) : null; } catch {}
          resolve({ status: res.statusCode, headers: res.headers, body: parsed });
        });
      });
      req.on('error', reject);
      req.on('timeout', () => req.destroy(new Error('Request timeout')));
      if (payload) req.write(payload);
      req.end();
    });

    if (retryOn.includes(response.status) && attempt < 4) {
      const retryAfter = Number(response.headers['retry-after'] || 0);
      const delayMs = retryAfter > 0 ? retryAfter * 1000 : (500 * Math.pow(2, attempt));
      await new Promise(r => setTimeout(r, delayMs));
      return this.request(method, pathname, body, query, attempt + 1, { retryOn });
    }
    if (this.verbose) console.log(`${method} ${url.pathname}${url.search} -> ${response.status}`);
    if (
      response.status >= 200 &&
      response.status < 300 &&
      response.body &&
      typeof response.body === 'object' &&
      Object.prototype.hasOwnProperty.call(response.body, 'data')
    ) {
      response.body = response.body.data;
    }
    return response;
  }

  listCampaigns(limit = 100, startingAfter) {
    const query = { limit };
    if (startingAfter) query.starting_after = startingAfter;
    return this.request('GET', '/campaigns', null, query);
  }

  getCampaign(id) {
    return this.request('GET', `/campaigns/${id}`);
  }

  // Every write through the OS outreach gateway must wrap its Instantly body
  // as {"payload": {...}} — the gateway's request model requires the field
  // and answers a raw Instantly body with a FastAPI 422. Centralized here so
  // no new write method can forget the wrapper. Bodyless POSTs
  // (activate/pause) send no body at all.
  writeRequest(method, pathname, payload, options) {
    return this.request(method, pathname, { payload }, null, 0, options);
  }

  createCampaign(payload) {
    return this.writeRequest('POST', '/campaigns', payload, { retryOn: RETRY_NOT_PROCESSED });
  }

  patchCampaign(id, payload) {
    return this.writeRequest('PATCH', `/campaigns/${id}`, payload);
  }

  activateCampaign(id) {
    return this.request('POST', `/campaigns/${id}/activate`);
  }

  pauseCampaign(id) {
    return this.request('POST', `/campaigns/${id}/pause`);
  }

  // Deletes only a draft that never sent (the gateway answers 409 otherwise).
  // A 5xx may come after the delete happened, so only "rate limited" is
  // retried; the caller reads the campaign back before trying again.
  deleteCampaign(id) {
    return this.request('DELETE', `/campaigns/${id}`, null, null, 0, { retryOn: RETRY_NOT_PROCESSED });
  }

  addLeadsToCampaign(payload) {
    return this.writeRequest('POST', '/leads/add', payload, { retryOn: RETRY_NOT_PROCESSED });
  }

  deleteLead(id) {
    return this.request('DELETE', `/leads/${id}`, null, null, 0, { retryOn: RETRY_NOT_PROCESSED });
  }

  // fields: first_name, last_name, company_name, website, personalization,
  // custom_variables. The gateway rejects any other key.
  updateLead(id, fields) {
    return this.writeRequest('PATCH', `/leads/${id}`, fields);
  }

  listEmails(query) {
    return this.request('GET', '/emails', null, query);
  }

  // Sends an email. A 5xx or timeout may come after Instantly already sent it,
  // so only "rate limited" (not processed) is retried; anything else goes back
  // to the caller, which treats a 5xx as an unknown outcome.
  replyToEmail(payload) {
    return this.writeRequest('POST', '/emails/reply', payload, { retryOn: RETRY_NOT_PROCESSED });
  }

  analyticsOverview(ids, extra = {}) {
    const campaignId = Array.isArray(ids) ? ids.find(Boolean) : ids;
    return this.request('GET', `/campaigns/${campaignId}/analytics/overview`, null, extra);
  }

  campaignAnalytics(id, extra = {}) {
    return this.request('GET', `/campaigns/${id}/analytics`, null, extra);
  }

  sendingStatus(id) {
    return this.request('GET', `/campaigns/${id}/sending-status`);
  }

  listAccounts(limit = 100, query = {}) {
    const params = { limit, ...query };
    if (params.status != null && params.status_filter == null) {
      params.status_filter = params.status;
    }
    delete params.status;
    return this.request('GET', '/accounts', null, params);
  }

  createCustomTag(payload) {
    return this.writeRequest('POST', '/custom-tags', payload, { retryOn: RETRY_NOT_PROCESSED });
  }

  listCustomTags(limit = 100, startingAfter) {
    const query = { limit };
    if (startingAfter) query.starting_after = startingAfter;
    return this.request('GET', '/custom-tags', null, query);
  }

  toggleTagResource(payload) {
    return this.writeRequest('POST', '/custom-tags/toggle-resource', payload);
  }

  listLeads(campaignId, { limit = 100, starting_after } = {}) {
    const query = { campaign_id: campaignId, limit };
    if (starting_after) query.starting_after = starting_after;
    return this.request('GET', '/leads', null, query);
  }

  /**
   * Lowercased emails of the leads already in a campaign. ok=false means the
   * complete list could not be read (#3790), so the caller cannot tell "empty"
   * from "unknown" and must not treat the set as complete.
   */
  listLeadRows(campaignId) {
    return listLeadRows(this, campaignId);
  }

  async listLeadEmails(campaignId) {
    const result = await this.listLeadRows(campaignId);
    return { ok: result.ok, emails: new Set(result.rows.map(row => row.email.trim().toLowerCase())) };
  }

  getRecipientExclusion(campaignId, leadId) {
    return this.request('GET', `/campaigns/${campaignId}/leads/${leadId}/exclusion`, null, null, 0, { retryOn: [] });
  }

  excludeRecipient(campaignId, leadId) {
    // Semantic OS contract, not the generic provider payload wrapper. Never
    // automatically replay a write with an uncertain outcome.
    return this.request('POST', `/campaigns/${campaignId}/leads/${leadId}/exclusion`,
      { intent: 'confirmed_opt_out' }, null, 0, { retryOn: [] });
  }

  /**
   * Count leads in a campaign by paginating through all results.
   * Returns { ok, status, total, contacted, not_contacted } where
   * "contacted" means the lead has been reached by the sending sequence.
   * ok=false means the FIRST page could not be read — callers must be able
   * to tell "leads read surface down" (issue #3790: GET /leads can 404 at
   * the gateway) apart from "campaign genuinely has zero leads"; treating a
   * read outage as zero once turned into a false import-failure diagnosis.
   */
  async countLeads(campaignId) {
    let total = 0;
    let contacted = 0;
    let contact_activity_unknown = 0;
    let cursor = undefined;
    let pages = 0;
    let status = null;
    const cursors = new Set();
    const identities = new Set();
    const emails = new Set();
    while (true) {
      const res = await this.listLeads(campaignId, { limit: 100, starting_after: cursor });
      status = res.status;
      if (!(res.status >= 200 && res.status < 300)) break;
      const items = Array.isArray(res.body) ? res.body : res.body?.items;
      if (!Array.isArray(items)) { status = null; break; }
      pages += 1;
      if (!items.length) break;
      const lastId = items[items.length - 1]?.id;
      if (lastId && cursors.has(lastId)) {
        status = null;
        break;
      }
      if (lastId) cursors.add(lastId);
      let invalid = false;
      for (const lead of items) {
        const email = typeof lead?.email === 'string' ? lead.email.trim().toLowerCase() : null;
        const id = typeof lead?.id === 'string' && lead.id ? lead.id : email;
        if (!id || identities.has(id) || (email && emails.has(email))
          || ['campaign', 'campaign_id'].some(key => lead[key] != null && lead[key] !== campaignId)) {
          invalid = true; break;
        }
        identities.add(id);
        if (email) emails.add(email);
        total++;
        if (isContactedLead(lead)) contacted++;
        else if (!(Object.hasOwn(lead, 'timestamp_last_contact') && lead.timestamp_last_contact == null)
          && !(Object.hasOwn(lead.status_summary || {}, 'lastStep') && lead.status_summary.lastStep == null)
          && lead.lead_status !== 'Not Contacted' && lead.status !== 'not_contacted') contact_activity_unknown++;
      }
      if (invalid || (!lastId && items.length >= 100)) { status = null; break; }
      if (items.length < 100) break;
      if (pages >= MAX_LEAD_PAGES) {
        status = null; // cursor ignored or no end in sight: the count is a floor
        break;
      }
      cursor = lastId;
    }
    const ok = pages > 0;
    // An interrupted or invalid population is a floor, not an exact count.
    // Activity can separately be unknown even with complete identity pages.
    const partial = ok && !(status >= 200 && status < 300);
    return { ok, partial, status, total, contacted, contact_activity_unknown, not_contacted: total - contacted };
  }
}

// Instantly API v2 leads carry no "Contacted" status: `status` stays 1
// (active) after the first send. A lead has been reached once it shows send
// or reply activity: the same marks and counters the tools gateway checks
// before a lead delete (_instantly_lead_contacted), plus the step recorded in
// status_summary. The older fields are kept for other payload shapes.
const LEAD_ACTIVITY_MARKS = [
  'timestamp_last_contact', 'timestamp_last_reply', 'timestamp_last_open',
  'timestamp_last_click', 'last_step_id', 'last_step_from', 'last_step_timestamp_executed',
];
const LEAD_ACTIVITY_COUNTS = ['email_reply_count', 'email_open_count', 'email_click_count'];

function isContactedLead(lead) {
  return Boolean(
    LEAD_ACTIVITY_MARKS.some((k) => lead[k])
    || LEAD_ACTIVITY_COUNTS.some((k) => typeof lead[k] === 'number' && lead[k] > 0)
    || lead.status_summary?.lastStep?.stepID
    || lead.lead_status === 'Contacted' || lead.status === 'contacted'
    || (lead.subsequence_status && lead.subsequence_status !== '0'),
  );
}

// Contacted count for a utilization ratio when the leads API supplies the
// total (lead_stats null, #3790). Takes the larger of analytics
// contacted_count and the per-lead count. Analytics more than 50% above the
// campaign's leads is likely workspace-level (see monitor-campaign) and is
// ignored; within that margin it is capped so utilization stays <= 100%.
function contactedForUtilization(analyticsContacted, counts) {
  const analytics = analyticsContacted > counts.total * 1.5
    ? 0
    : Math.min(analyticsContacted || 0, counts.total);
  return Math.max(analytics, counts.contacted);
}

module.exports = { InstantlyClient, isContactedLead, contactedForUtilization };
