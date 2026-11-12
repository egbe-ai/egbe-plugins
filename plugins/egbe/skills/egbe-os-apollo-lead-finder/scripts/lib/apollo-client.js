const connectionHeaders = require('./connection-identity');
const https = require("https");
const http = require("http");
const { URL } = require("url");

// Apollo's search page size cap. searchAllPeople requests this many per page
// and uses it as the "full page" signal when pagination metadata is missing.
const PER_PAGE = 100;

// The gateway's per-claw daily quota answers 429 with "limit_exceeded:<resource>"
// (or "limit_not_configured:<resource>"). Unlike Apollo's own rate limit it does
// not clear in seconds, so retrying would only wait out the day.
function isDailyQuotaError(response) {
  return (
    response.status === 429 &&
    /limit_(exceeded|not_configured):/.test(JSON.stringify(response.body ?? ""))
  );
}

class ApolloClient {
  constructor({
    osUrl,
    osApiKey,
    connectionEnvFile = null,
    timeoutMs = 30000,
    timeBudgetMs = 90000,
    maxRetries = 4,
    now = Date.now,
    sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    verbose = false,
  }) {
    if (!osUrl) throw new Error("Missing OS_URL");
    if (!osApiKey) throw new Error("Missing OS_API_KEY");
    this.baseUrl = `${osUrl.replace(/\/$/, "")}/outreach/apollo`;
    this.osApiKey = osApiKey;
    this.identityHeaders = connectionHeaders(osUrl, connectionEnvFile);
    this.timeoutMs = timeoutMs;
    if (!Number.isFinite(timeBudgetMs) || timeBudgetMs <= 0)
      throw new Error("timeBudgetMs must be a positive number");
    if (!Number.isInteger(maxRetries) || maxRetries < 0)
      throw new Error("maxRetries must be a non-negative integer");
    this.now = now;
    this.sleep = sleep;
    this.deadline = now() + timeBudgetMs;
    this.maxRetries = maxRetries;
    this.verbose = verbose;
  }

  async request(method, pathname, body = null, attempt = 0) {
    const remaining = this.deadline - this.now();
    if (remaining <= 0) return { status: 0, stop_reason: "time_budget", body: null };
    const url = new URL(String(pathname || "").replace(/^\/+/, ""), `${this.baseUrl}/`);
    const transport = url.protocol === "http:" ? http : https;
    const payload = body == null ? null : JSON.stringify(body);
    const options = {
      method,
      hostname: url.hostname,
      port: url.port || (url.protocol === "http:" ? 80 : 443),
      path: url.pathname + url.search,
      headers: {
        ...(url.origin === new URL(this.baseUrl).origin ? this.identityHeaders : {}),
        Authorization: `Bearer ${this.osApiKey}`,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
      },
      timeout: Math.min(this.timeoutMs, remaining),
    };
    if (payload) options.headers["Content-Length"] = Buffer.byteLength(payload);

    const response = await new Promise((resolve, reject) => {
      const req = transport.request(options, (res) => {
        let data = "";
        res.on("data", (c) => (data += c));
        res.on("end", () => {
          let parsed = data;
          try {
            parsed = data ? JSON.parse(data) : null;
          } catch {}
          clearTimeout(deadlineTimer);
          resolve({
            status: res.statusCode,
            headers: res.headers,
            body: parsed,
          });
        });
        res.on("error", (error) => { clearTimeout(deadlineTimer); reject(error); });
      });
      // A socket timeout alone can be kept alive by a slow response stream.
      const deadlineTimer = setTimeout(() => req.destroy(new Error("Request time budget exceeded")), options.timeout);
      req.on("error", (error) => { clearTimeout(deadlineTimer); reject(error); });
      req.on("timeout", () => req.destroy(new Error("Request timeout")));
      if (payload) req.write(payload);
      req.end();
    });

    const retryable = [408, 429, 500, 502, 503, 504].includes(response.status);
    if (retryable && attempt < this.maxRetries && !isDailyQuotaError(response)) {
      const retryHeader = response.headers["retry-after"];
      const retryAfter = Number(retryHeader) || Math.max(0, (Date.parse(retryHeader) - this.now()) / 1000) || 0;
      let delayMs;
      if (retryAfter > 0) {
        delayMs = retryAfter * 1000;
      } else if (response.status === 429) {
        // Apollo returns 429 without Retry-After in some workspaces.
        // The default 0.5/1/2/4s backoff is far too short — Apollo's
        // typical cooldown is 60s+, so retrying inside the cooldown
        // just re-trips the limit and burns the retry budget. Floor
        // at 60s for 429s; keep the doubled backoff for non-429 cases.
        delayMs = Math.max(60_000, 500 * Math.pow(2, attempt));
      } else {
        delayMs = 500 * Math.pow(2, attempt);
      }
      if (this.verbose)
        console.error(
          `Retry ${attempt + 1} after ${delayMs}ms (status ${response.status})`,
        );
      if (delayMs >= this.deadline - this.now())
        return { ...response, stop_reason: "time_budget" };
      await this.sleep(delayMs);
      return this.request(method, pathname, body, attempt + 1);
    }
    if (this.verbose)
      console.error(`${method} ${url.pathname} -> ${response.status}`);
    if (
      response.status >= 200 &&
      response.status < 300 &&
      response.body &&
      typeof response.body === "object" &&
      Object.prototype.hasOwnProperty.call(response.body, "data")
    ) {
      response.body = response.body.data;
    }
    return response;
  }

  /**
   * Search for people. Does NOT return emails — use enrich for that.
   * Uses project search quota; this is not an offline dry run.
   * Max 100 per page, max 500 pages.
   */
  searchPeople(params) {
    return this.request("POST", "/people/search", params);
  }

  /**
   * Enrich a single person to get email + phone.
   * Uses project enrichment quota and may incur provider charges.
   */
  enrichPerson(params) {
    return this.request("POST", "/people/match", params);
  }

  /**
   * Bulk enrich up to 10 people per call.
   * More efficient than single enrichment.
   */
  bulkEnrichPeople(details) {
    return this.request("POST", "/people/bulk_match", { details });
  }

  /**
   * Paginated search: fetches all pages up to maxPages or maxResults.
   * Returns people plus completeness; onProgress can persist each page.
   */
  async searchAllPeople(params, { maxPages = 10, maxResults = 500, onProgress = () => {} } = {}) {
    const allPeople = [];
    const seenIds = new Set();
    const state = { people: allPeople, complete: false, stop_reason: "in_progress", next_page: 1 };
    const finish = async (complete, stopReason) => {
      state.complete = complete;
      state.stop_reason = stopReason;
      await onProgress(state);
      return state;
    };
    for (let page = 1; page <= maxPages; page++) {
      state.next_page = page;
      if (this.now() >= this.deadline) return finish(false, "time_budget");
      let res;
      try {
        res = await this.searchPeople({ ...params, page, per_page: PER_PAGE });
      } catch {
        return finish(false, this.now() >= this.deadline ? "time_budget" : "network_error");
      }
      if (res.status !== 200) {
        state.error_status = res.status;
        return finish(false, responseStopReason(res));
      }
      if (!Array.isArray(res.body?.people)) return finish(false, "invalid_response");
      const people = res.body.people;
      state.next_page = page + 1;
      if (!people.length) return finish(true, "search_exhausted");
      // Duplicate guard: if the gateway ignores the page param it returns the
      // same people for every page. Track ids across pages; a page that adds
      // zero new people means we are looping, not paging — stop.
      let added = 0;
      for (const person of people) {
        const id = person?.id;
        if (id != null) {
          if (seenIds.has(id)) continue;
          seenIds.add(id);
        }
        if (allPeople.length < maxResults) allPeople.push(person);
        added += 1;
      }
      if (!added) return finish(false, "repeated_page");
      if (allPeople.length >= maxResults) return finish(true, "max_results");
      // The OS gateway returns an empty pagination object, so `total_pages || 1`
      // silently capped every search at page 1 even though page=2 requests
      // return data. Only honor pagination when it is actually present.
      const totalPages = Number(res.body?.pagination?.total_pages);
      if (Number.isFinite(totalPages) && totalPages > 0 && page >= totalPages)
        return finish(true, "search_exhausted");
      // Full-page heuristic: without pagination metadata, a page shorter than
      // PER_PAGE means we have reached the end of the results.
      if (people.length < PER_PAGE) return finish(true, "search_exhausted");
      await onProgress(state);
    }
    return finish(false, "max_pages");
  }

  /**
   * Bulk enrich an array of people in batches of 10.
   * Respects rate limit with configurable delay between batches.
   * Returns matches, progress and the exact unprocessed input for recovery.
   */
  async bulkEnrichAll(people, { batchDelayMs = 1000, onProgress = () => {} } = {}) {
    // Validate the entire input before making a potentially paid request.
    const normalized = people.map(toMatchDetails);
    const state = { matches: [], processed_count: 0, complete: false,
      stop_reason: "in_progress", not_enriched: people.length, not_enriched_people: people.slice() };
    const checkpoint = async (complete, reason) => {
      state.complete = complete;
      state.stop_reason = reason;
      state.not_enriched_people = people.slice(state.processed_count);
      state.not_enriched = state.not_enriched_people.length;
      await onProgress(state);
      return state;
    };
    for (let i = 0; i < people.length; i += 10) {
      if (this.now() >= this.deadline) return checkpoint(false, "time_budget");
      const details = normalized.slice(i, i + 10);
      let res;
      try { res = await this.bulkEnrichPeople(details); }
      catch { return checkpoint(false, this.now() >= this.deadline ? "time_budget" : "network_error"); }
      if (res.status !== 200) {
        state.error_status = res.status;
        return checkpoint(false, responseStopReason(res));
      }
      if (!Array.isArray(res.body?.matches)) return checkpoint(false, "invalid_response");
      state.matches.push(...res.body.matches.filter(Boolean));
      state.processed_count += details.length;
      await checkpoint(false, "in_progress");
      if (i + 10 < people.length) {
        if (batchDelayMs >= this.deadline - this.now()) return checkpoint(false, "time_budget");
        await this.sleep(batchDelayMs);
      }
    }
    return checkpoint(true, "completed");
  }
}

function responseStopReason(response) {
  if (response.stop_reason) return response.stop_reason;
  if (isDailyQuotaError(response)) return "daily_quota";
  if (response.status === 429) return "rate_limited";
  if ([401, 403].includes(response.status)) return "authorization";
  return "provider_error";
}

function toMatchDetails(person) {
  if (!person || typeof person !== "object" || Array.isArray(person))
    throw new Error("Each enrichment input must be a person object");
  const details = {
    id: person.id || person.apollo_id,
    first_name: person.first_name,
    last_name: person.last_name,
    organization_name: person.organization?.name || person.organization_name || person.company_name || person.company,
    domain: person.organization?.primary_domain || person.domain || person.company_domain || person.website,
    linkedin_url: person.linkedin_url,
    reveal_personal_emails: false,
  };
  if (details.domain) {
    try { details.domain = new URL(/^https?:\/\//.test(details.domain) ? details.domain : `https://${details.domain}`).hostname; }
    catch { throw new Error("Invalid enrichment domain"); }
  }
  if (!details.id && !details.linkedin_url && !(details.first_name && details.last_name && (details.domain || details.organization_name)))
    throw new Error("Enrichment needs id/apollo_id, linkedin_url, or first_name + last_name + domain/company; display name alone is not enough");
  return details;
}

module.exports = { ApolloClient, isDailyQuotaError, responseStopReason, toMatchDetails };
