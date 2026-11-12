#!/usr/bin/env node
"use strict";
const connectionHeaders = require('./lib/connection-identity');
const connectionIdentityByConfig = new WeakMap();

/**
 * places-leads — Source business listings and public website contact candidates.
 *
 *   1. POST $OS_URL/search/places for each query (place names + place_ids)
 *   2. POST $OS_URL/tools/places/details per place (websiteUri, types, phone)
 *   3. Scrape each website (homepage + /contact + /about) for an email
 *   4. Filter traps, prefer personal over generic addresses, emit the same
 *      output contract as find-leads.js with email_status "unverified"
 *
 * Search, details and reviews have separate project quotas and operation costs.
 * The local processing cap is not a statement of available daily quota.
 *
 * Usage:
 *   node places-leads.js \
 *     --queries "real estate photographer austin;real estate photographer dallas" \
 *     --exclude-categories "headshot,wedding,portrait" \
 *     --max-places 60 --output leads.json [--env-file <path>] [--verbose]
 */

const https = require("https");
const http = require("http");
const dns = require("dns");
const path = require("path");
const { URL } = require("url");
const { isDailyQuotaError, responseStopReason } = require("./lib/apollo-client");
const { positiveInteger } = require("./lib/sourcing");
const {
  parseArgs,
  writeJson,
  isoNow,
  normalizeEmail,
  parseList,
  parseSemicolonList,
  readEnvFile,
  getOsConfig,
} = require("./lib/helpers");
const {
  GENERIC_LOCAL_PARTS,
  FREEMAIL_DOMAINS,
  classifyEmail,
  extractOwnerFirstName,
} = require("./lib/places-filters");

const BROWSER_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";
const FETCH_TIMEOUT_MS = 8000;
const MAX_REDIRECTS = 3;
const MAX_HTML_BYTES = 600_000;
// Places search returns at most 20 results per query (API page cap).
const SEARCH_PAGE_CAP = 20;
// The tools-gateway details default field mask has no primaryType/types, so
// request an explicit mask with everything the pipeline needs.
const DETAILS_FIELDS =
  "id,displayName,formattedAddress,websiteUri,nationalPhoneNumber,primaryType,types";
// Conservative: bounded TLD ({2,24} covers long ICANN TLDs the target ICP
// actually uses — .photography, .construction), single-case TLD label so a
// mixed-case sentence glued after the address ("jane@janephoto.com.Call")
// cannot be matched as the TLD, and the match may not continue with a word
// char (avoids swallowing text concatenated after the address in minified
// HTML).
const EMAIL_RE =
  /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(?:[a-z]{2,24}|[A-Z]{2,24})(?![A-Za-z0-9-])/g;

function fail(msg) {
  console.error(`FATAL: ${msg}`);
  process.exit(1);
}

/**
 * Authenticated OS request. Mirrors lib/apollo-client.js: retries transient
 * statuses with backoff and unwraps the OS `{code, message, data}` envelope.
 */
async function osRequest(cfg, method, pathname, body = null, attempt = 0) {
  if (Date.now() >= cfg.deadline) return { status: 0, stop_reason: "time_budget" };
  if (!connectionIdentityByConfig.has(cfg)) connectionIdentityByConfig.set(cfg, connectionHeaders(cfg.osUrl, cfg.connectionEnvFile));
  const url = new URL(cfg.osUrl.replace(/\/$/, "") + pathname);
  const transport = url.protocol === "http:" ? http : https;
  const payload = body == null ? null : JSON.stringify(body);
  const options = {
    method,
    hostname: url.hostname,
    port: url.port || (url.protocol === "http:" ? 80 : 443),
    path: url.pathname + url.search,
    headers: {
      ...connectionIdentityByConfig.get(cfg),
      Authorization: `Bearer ${cfg.osApiKey}`,
      "Content-Type": "application/json",
      "Cache-Control": "no-cache",
    },
    timeout: Math.min(30000, cfg.deadline - Date.now()),
  };
  if (payload) options.headers["Content-Length"] = Buffer.byteLength(payload);

  const response = await new Promise((resolve, reject) => {
    const req = transport.request(options, (res) => {
      let data = "";
      res.on("data", (c) => (data += c));
      res.on("end", () => {
        clearTimeout(deadlineTimer);
        let parsed = data;
        try {
          parsed = data ? JSON.parse(data) : null;
        } catch {}
        resolve({ status: res.statusCode, headers: res.headers, body: parsed });
      });
      res.on("error", (error) => { clearTimeout(deadlineTimer); reject(error); });
    });
    const deadlineTimer = setTimeout(() => req.destroy(new Error("Request time budget exceeded")), options.timeout);
    req.on("error", (error) => { clearTimeout(deadlineTimer); reject(error); });
    req.on("timeout", () => req.destroy(new Error("Request timeout")));
    if (payload) req.write(payload);
    req.end();
  });

  const retryable = [408, 429, 500, 502, 503, 504].includes(response.status);
  if (retryable && attempt < 3 && !isDailyQuotaError(response)) {
    const retryAfter = Number(response.headers["retry-after"] || 0);
    const delayMs = retryAfter > 0 ? retryAfter * 1000 : 1000 * Math.pow(2, attempt);
    if (delayMs >= cfg.deadline - Date.now()) return { ...response, stop_reason: "time_budget" };
    if (cfg.verbose)
      console.error(`Retry ${attempt + 1} after ${delayMs}ms (status ${response.status})`);
    await new Promise((r) => setTimeout(r, delayMs));
    return osRequest(cfg, method, pathname, body, attempt + 1);
  }
  if (cfg.verbose) console.error(`${method} ${url.pathname} -> ${response.status}`);
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

// --- SSRF guard -------------------------------------------------------------
// websiteUri comes from a third-party Places listing, and a public site can
// 302 to loopback / RFC1918 / link-local (cloud metadata) addresses. Mirror
// tools-gateway/app/providers/destination_urls.py: reject internal hosts up
// front, resolve DNS once per hop, refuse any non-public answer, and pin the
// connection to the vetted address (Host header + SNI keep the logical
// hostname) so a rebinding second lookup cannot redirect the request.

const INTERNAL_HOST_SUFFIXES = [".gcp.egbe.dev", ".hz.egbe.dev"];

function isGlobalIpv4(ip) {
  const octets = ip.split(".").map(Number);
  if (octets.length !== 4 || octets.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) {
    return false;
  }
  const [a, b] = octets;
  if (a === 0 || a === 10 || a === 127) return false;
  if (a === 100 && b >= 64 && b <= 127) return false; // CGNAT 100.64/10
  if (a === 169 && b === 254) return false; // link-local incl. metadata
  if (a === 172 && b >= 16 && b <= 31) return false;
  if (a === 192 && b === 168) return false;
  if (a === 192 && b === 0) return false; // 192.0.0/24 + 192.0.2/24 doc
  if (a === 198 && (b === 18 || b === 19)) return false; // benchmarking
  if (a === 198 && b === 51) return false; // 198.51.100/24 doc
  if (a === 203 && b === 0) return false; // 203.0.113/24 doc
  if (a >= 224) return false; // multicast, reserved, broadcast
  return true;
}

function isGlobalIp(ip) {
  const value = String(ip || "").toLowerCase();
  if (!value) return false;
  if (value.includes(":")) {
    const mapped = value.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/);
    if (mapped) return isGlobalIpv4(mapped[1]);
    if (value === "::" || value === "::1") return false;
    if (/^f[cd]/.test(value)) return false; // fc00::/7 unique-local
    if (/^fe[89ab]/.test(value)) return false; // fe80::/10 link-local
    if (/^ff/.test(value)) return false; // multicast
    if (value.startsWith("2001:db8")) return false; // documentation
    return /^[23]/.test(value); // 2000::/3 global unicast
  }
  return isGlobalIpv4(value);
}

/**
 * Resolve a hostname and return one vetted public address, or null when the
 * host is internal, unresolvable, or ANY answer is a non-public address.
 */
async function resolvePublicAddress(hostname) {
  const host = String(hostname || "")
    .toLowerCase()
    .replace(/\.$/, "");
  if (!host || host === "localhost" || host.endsWith(".localhost")) return null;
  if (
    INTERNAL_HOST_SUFFIXES.some(
      (suffix) => host === suffix.slice(1) || host.endsWith(suffix),
    )
  ) {
    return null;
  }
  if (/^[\d.]+$/.test(host) || host.includes(":")) {
    const literal = host.replace(/^\[|\]$/g, "");
    return isGlobalIp(literal) ? literal : null;
  }
  let answers;
  try {
    answers = await dns.promises.lookup(host, { all: true, verbatim: true });
  } catch {
    return null;
  }
  if (!answers.length || answers.some((entry) => !isGlobalIp(entry.address))) {
    return null;
  }
  return answers[0].address;
}

/**
 * Plain GET with a browser-ish User-Agent. Follows up to MAX_REDIRECTS with
 * every hop re-validated and pinned to a vetted public address, skips
 * non-HTML responses, truncates huge pages. Resolves to the HTML string or
 * null — never rejects.
 */
async function fetchHtml(rawUrl, redirectsLeft = MAX_REDIRECTS, deadline = Infinity) {
  if (Date.now() >= deadline) return null;
  let url;
  try {
    url = new URL(rawUrl);
  } catch {
    return null;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return null;
  if (url.username || url.password) return null;
  let dnsTimer;
  const address = await Promise.race([
    resolvePublicAddress(url.hostname),
    new Promise((resolve) => { dnsTimer = setTimeout(() => resolve(null), Math.min(FETCH_TIMEOUT_MS, deadline - Date.now())); }),
  ]);
  clearTimeout(dnsTimer);
  if (!address) return null;
  const transport = url.protocol === "http:" ? http : https;

  const outcome = await new Promise((resolve) => {
    let settled = false;
    let deadlineTimer;
    const settle = (value) => {
      if (!settled) {
        settled = true;
        clearTimeout(deadlineTimer);
        resolve(value);
      }
    };
    const req = transport.get(
      {
        host: address,
        port: url.port || (url.protocol === "http:" ? 80 : 443),
        path: url.pathname + url.search,
        headers: {
          Host: url.host,
          "User-Agent": BROWSER_UA,
          Accept: "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        },
        ...(url.protocol === "https:" ? { servername: url.hostname } : {}),
        timeout: Math.min(FETCH_TIMEOUT_MS, Math.max(1, deadline - Date.now())),
      },
      (res) => {
        const status = res.statusCode || 0;
        const location = res.headers.location;
        if (status >= 300 && status < 400 && location && redirectsLeft > 0) {
          res.resume();
          let next;
          try {
            next = new URL(location, url).toString();
          } catch {
            return settle({ html: null });
          }
          return settle({ redirect: next });
        }
        const contentType = String(res.headers["content-type"] || "");
        if (status !== 200 || (contentType && !contentType.includes("text/html"))) {
          res.resume();
          return settle({ html: null });
        }
        let data = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          data += chunk;
          if (data.length > MAX_HTML_BYTES) {
            settle({ html: data });
            req.destroy();
          }
        });
        res.on("end", () => settle({ html: data }));
        res.on("error", () => settle({ html: data || null }));
      },
    );
    deadlineTimer = setTimeout(() => { settle({ html: null }); req.destroy(); }, Math.min(FETCH_TIMEOUT_MS, Math.max(1, deadline - Date.now())));
    req.on("timeout", () => req.destroy());
    req.on("error", () => settle({ html: null }));
  });

  if (outcome.redirect) {
    // Recurse so the redirect target goes through the same host/DNS vetting
    // and address pinning as the original URL.
    return fetchHtml(outcome.redirect, redirectsLeft - 1, deadline);
  }
  return outcome.html;
}

/** Emails from mailto: links plus a conservative regex over the raw HTML. */
function extractEmails(html) {
  const out = new Set();
  const source = String(html || "");
  const mailtoRe = /mailto:([^"'\s<>]+)/gi;
  let m;
  while ((m = mailtoRe.exec(source))) {
    let candidate = m[1].split("?")[0];
    try {
      candidate = decodeURIComponent(candidate);
    } catch {}
    for (const hit of candidate.match(EMAIL_RE) || []) out.add(normalizeEmail(hit));
  }
  for (const hit of source.match(EMAIL_RE) || []) out.add(normalizeEmail(hit));
  return [...out].filter(Boolean);
}

/** Crude but dependency-free HTML -> text for owner-name extraction. */
function htmlToText(html) {
  return String(html || "")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&(?:#39|#8217|apos|rsquo);/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function pageTitle(html) {
  const m = String(html || "").match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  return m ? htmlToText(m[1]) : "";
}

/** Best-effort {city, state, country} from a Places formattedAddress. */
function parseAddress(formatted) {
  const parts = String(formatted || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length < 3) return { city: "", state: "", country: "" };
  return {
    city: parts[parts.length - 3],
    state: parts[parts.length - 2].replace(/[\d-]+/g, "").trim(),
    country: parts[parts.length - 1],
  };
}

function toDomain(websiteUri) {
  try {
    return new URL(websiteUri).hostname.replace(/^www\./, "");
  } catch {
    return String(websiteUri || "");
  }
}

/**
 * Heuristic ranking, not evidence of ownership or suitability:
 *   0. personal local-part on the site's own domain
 *   1. personal-looking on a freemail provider
 *   2. generic on the site's own domain (GENERIC_LOCAL_PARTS order)
 *   3. generic elsewhere
 *   4. personal on an unrelated non-freemail domain — usually a third party
 *      embedded in the page (designer credit, partner studio), last resort
 */
function pickEmail(candidates, siteDomain, preference = "personal") {
  const site = String(siteDomain || "").toLowerCase();
  let best = null;
  let bestScore = Infinity;
  for (const email of candidates) {
    const kind = classifyEmail(email);
    if (kind === "trap") continue;
    if (preference === "first") return { email, kind };
    const domain = String(email).toLowerCase().split("@")[1] || "";
    const onSite =
      !!site && (domain === site || domain.endsWith(`.${site}`) || site.endsWith(`.${domain}`));
    const genericRank = Math.max(
      0,
      GENERIC_LOCAL_PARTS.indexOf(String(email).toLowerCase().split("@")[0]),
    );
    let score;
    if (kind === "personal" && onSite) score = 0;
    else if (kind === "personal" && FREEMAIL_DOMAINS.has(domain)) score = 1;
    else if (kind === "generic" && onSite) score = 2 + genericRank / 100;
    else if (kind === "generic") score = 3 + genericRank / 100;
    else score = 4;
    if (preference === "generic" && kind === "generic") score -= 3;
    if (score < bestScore) {
      bestScore = score;
      best = { email, kind };
    }
  }
  return best;
}

async function main() {
  const args = parseArgs(process.argv);
  const verbose = !!args.verbose;

  const env = args["env-file"] ? readEnvFile(path.resolve(args["env-file"])) : {};
  const os = getOsConfig({ ...env, ...process.env });
  if (os.missing.length)
    fail(`${os.missing.join(" and ")} not set. Export them or pass --env-file.`);
  const cfg = { osUrl: os.osUrl, osApiKey: os.osApiKey, verbose,
    deadline: Date.now() + positiveInteger(args["time-budget-ms"], 90000, "--time-budget-ms"),
    connectionEnvFile: args["env-file"] ? path.resolve(args["env-file"]) : null };

  const queries = parseSemicolonList(args.queries);
  if (!queries.length) fail('--queries is required (semicolon-separated, e.g. "a;b")');
  const excludeCategories = parseList(args["exclude-categories"]).map((t) =>
    t.toLowerCase(),
  );
  // A local bound on work, independent of current project provider quotas.
  const MAX_PLACES_CAP = 200;
  const maxPlacesRaw =
    args["max-places"] == null ? 60 : Number(args["max-places"]);
  if (!Number.isInteger(maxPlacesRaw) || maxPlacesRaw <= 0) {
    fail(
      `--max-places must be a positive integer, got "${args["max-places"]}"`,
    );
  }
  const maxPlaces = Math.min(maxPlacesRaw, MAX_PLACES_CAP);
  if (maxPlaces < maxPlacesRaw) {
    console.error(
      `--max-places clamped from ${maxPlacesRaw} to ${MAX_PLACES_CAP} (local script cap, not a provider quota)`,
    );
  }
  const outputPath = args.output ? path.resolve(args.output) : null;
  const emailPreference = args["email-preference"] || "personal";
  if (!["personal", "generic", "first"].includes(emailPreference)) fail("--email-preference must be personal, generic or first");
  const drops = { details_failed: 0, scrape_failed: 0, category: 0, no_website: 0, no_email: 0, duplicate_email: 0 };
  let sitesScraped = 0;
  let emailsFound = 0;
  const seenEmails = new Set();
  const leads = [];
  const pendingPlaces = new Map();
  const pendingQueries = new Set(queries);
  let stopReason = null;
  const result = { leads, meta: {
    searched_at: isoNow(), search_params: { queries, exclude_categories: excludeCategories,
      max_places: maxPlaces, email_preference: emailPreference }, source: "places",
    complete: false, stop_reason: "in_progress", total_found: 0, enriched: 0,
    not_enriched: 0, not_enriched_people: [], sites_scraped: 0, leads_with_email: 0,
    email_status_filter: ["unverified"], search_failures: 0, drops,
    pending_queries: queries.slice(), not_processed_places: [],
  } };
  const checkpoint = () => {
    Object.assign(result.meta, { total_found: places.size, sites_scraped: sitesScraped,
      leads_with_email: leads.length, search_failures: searchFailures,
      pending_queries: [...pendingQueries], not_processed_places: [...pendingPlaces.values()] });
    if (outputPath) writeJson(outputPath, result);
  };

  // --- Step 1: Places search (one quota unit per query) ---
  const places = new Map(); // place_id -> {place_id, name, address}
  let searchSuccesses = 0;
  let searchFailures = 0;
  let lastSearchFailure = null;
  checkpoint();
  for (const query of queries) {
    if (places.size >= maxPlaces) {
      console.error(`Skipping "${query}": --max-places ${maxPlaces} reached`);
      pendingQueries.delete(query);
      continue;
    }
    let res;
    try { res = await osRequest(cfg, "POST", "/search/places", {
      query,
      max_results: Math.min(SEARCH_PAGE_CAP, maxPlaces - places.size),
    }); } catch { res = { status: 0, stop_reason: Date.now() >= cfg.deadline ? "time_budget" : "network_error" }; }
    if (res.status !== 200) {
      // Auth/quota failure hits every remaining query identically — stop
      // now instead of logging N times and writing a fake-empty result.
      searchFailures += 1;
      stopReason = responseStopReason(res);
      lastSearchFailure = `${res.status} ${JSON.stringify(res.body)}`;
      console.error(`Search failed for "${query}": ${lastSearchFailure}`);
      checkpoint();
      if ([401, 403, 429, 0].includes(res.status)) break;
      continue;
    }
    if (!Array.isArray(res.body?.results)) { searchFailures++; stopReason = "invalid_response"; checkpoint(); continue; }
    pendingQueries.delete(query);
    searchSuccesses += 1;
    const results = res.body?.results || [];
    let added = 0;
    for (const r of results) {
      const placeId = r?.metadata?.place_id;
      if (!placeId || places.has(placeId)) continue;
      if (places.size >= maxPlaces) break;
      const place = {
        place_id: placeId,
        name: r.title || "",
        address: r.snippet || "",
      };
      places.set(placeId, place);
      pendingPlaces.set(placeId, place);
      added += 1;
    }
    console.error(`Query "${query}": ${results.length} places (${added} new)`);
    checkpoint();
  }
  console.error(`${places.size} unique places found. Fetching details...`);

  // --- Steps 2-5: details -> category filter -> scrape -> classify ---
  for (const place of places.values()) {
    try {
      const res = await osRequest(cfg, "POST", "/tools/places/details", {
        place_id: place.place_id,
        fields: DETAILS_FIELDS,
      });
      if (res.status !== 200) {
        drops.details_failed += 1;
        stopReason = responseStopReason(res);
        if (verbose)
          console.error(`Details failed for ${place.place_id}: ${res.status}`);
        if ([401, 403, 429, 0].includes(res.status)) break;
        continue;
      }
      if (!res.body || typeof res.body !== "object") { drops.details_failed++; stopReason = "invalid_response"; continue; }
      const details = res.body || {};
      const name = details.displayName?.text || place.name;
      const types = [details.primaryType || "", ...(details.types || [])];
      const categoryHaystack = [name, ...types].join(" ").toLowerCase();
      if (excludeCategories.some((t) => categoryHaystack.includes(t))) {
        drops.category += 1;
        pendingPlaces.delete(place.place_id);
        if (verbose) console.error(`Excluded by category: ${name}`);
        continue;
      }
      const websiteUri = details.websiteUri || "";
      if (!websiteUri) {
        drops.no_website += 1;
        pendingPlaces.delete(place.place_id);
        if (verbose) console.error(`No website: ${name}`);
        continue;
      }

      // Homepage + the two pages solo operators put their address/name on.
      const pageUrls = [websiteUri];
      try {
        pageUrls.push(new URL("/contact", websiteUri).toString());
        pageUrls.push(new URL("/about", websiteUri).toString());
      } catch {}
      const htmls = (await Promise.all(pageUrls.map((u) => fetchHtml(u, MAX_REDIRECTS, cfg.deadline)))).filter(
        Boolean,
      );
      if (!htmls.length) {
        drops.scrape_failed += 1;
        stopReason = Date.now() >= cfg.deadline ? "time_budget" : "website_unavailable";
        continue;
      }
      sitesScraped += 1;

      const candidates = new Set();
      for (const html of htmls) for (const e of extractEmails(html)) candidates.add(e);
      emailsFound += candidates.size;

      const picked = pickEmail([...candidates], toDomain(websiteUri), emailPreference);
      pendingPlaces.delete(place.place_id);
      if (!picked) {
        drops.no_email += 1;
        if (verbose) console.error(`No usable email: ${name} (${websiteUri})`);
        continue;
      }
      if (seenEmails.has(picked.email)) {
        drops.duplicate_email += 1;
        continue;
      }
      seenEmails.add(picked.email);

      const text = `${htmls.map(pageTitle).join(" ")} ${htmls
        .map(htmlToText)
        .join(" ")}`;
      const { city, state, country } = parseAddress(
        details.formattedAddress || place.address,
      );
      leads.push({
        email: picked.email,
        first_name: "",
        last_name: "",
        company_name: name,
        website: toDomain(websiteUri),
        title: "",
        seniority: "",
        linkedin_url: "",
        city,
        state,
        country,
        industry: details.primaryType || "",
        company_size: null,
        email_status: "unverified",
        apollo_id: "",
        // Extended fields (ignored by Instantly, useful for analytics)
        place_id: place.place_id,
        phone: details.nationalPhoneNumber || "",
        email_kind: picked.kind,
        email_selection: `${emailPreference}_heuristic`,
        name_candidate: extractOwnerFirstName(text, name),
        name_candidate_source: "page_text_english_heuristic",
        website_url: websiteUri,
        address_source: "formatted_address_heuristic",
      });
      if (verbose) console.error(`Lead: ${picked.email} (${picked.kind}) — ${name}`);
    } catch (e) {
      drops.details_failed += 1;
      stopReason = Date.now() >= cfg.deadline ? "time_budget" : "network_error";
      console.error(`Place ${place.place_id} failed: ${e.message}`);
    } finally {
      checkpoint();
    }
  }
  result.meta.complete = pendingQueries.size === 0 && pendingPlaces.size === 0;
  result.meta.stop_reason = result.meta.complete ? (places.size >= maxPlaces ? "max_places" : "completed") : stopReason || "incomplete";
  checkpoint();

  const dropSummary = Object.entries(drops)
    .map(([k, v]) => `${k}=${v}`)
    .join(" ");
  console.error(
    `Summary: ${places.size} places seen, ${sitesScraped} sites scraped, ` +
      `${emailsFound} emails found, ${leads.length} leads emitted. Drops: ${dropSummary}`,
  );

  if (outputPath) {
    writeJson(outputPath, result);
    console.error(`Wrote ${leads.length} leads to ${outputPath}`);
  } else {
    console.log(JSON.stringify(result, null, 2));
  }
  process.exitCode = result.meta.complete ? 0 : 2;
}

if (require.main === module) main().catch((e) => {
  console.error(e);
  process.exit(1);
});

module.exports = { isGlobalIp, resolvePublicAddress, fetchHtml, extractEmails, pickEmail };
