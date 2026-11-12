"use strict";

const path = require("path");
const { ApolloClient, toMatchDetails } = require("./apollo-client");
const { parseArgs, readJson, writeJson, isoNow, toLeadRecord, parseList,
  parseSemicolonList, readEnvFile, getOsConfig } = require("./helpers");

function positiveInteger(value, fallback, flag) {
  const number = value === undefined ? fallback : Number(value);
  if (!Number.isSafeInteger(number) || number <= 0) throw new Error(`${flag} must be a positive integer`);
  return number;
}

function searchParams(args) {
  if (args.config) {
    const config = readJson(path.resolve(args.config));
    if (!config) throw new Error(`Config file not found: ${args.config}`);
    const params = config.search || config;
    if (!params || typeof params !== "object" || Array.isArray(params)) throw new Error("Search config must be an object");
    return params;
  }
  const params = {};
  const flags = {
    titles: "person_titles", "not-titles": "person_not_titles", seniorities: "person_seniorities",
    locations: "person_locations", "not-locations": "person_not_locations", domains: "q_organization_domains_list",
    "org-locations": "organization_locations", "org-names": "organization_names", keywords: "keywords",
    industries: "industry_tag_ids", technologies: "currently_using_any_of_technology_uids",
    "email-status": "contact_email_status",
  };
  for (const [flag, key] of Object.entries(flags)) if (args[flag]) params[key] = parseList(args[flag]);
  if (args["employee-ranges"]) params.organization_num_employees_ranges = parseSemicolonList(args["employee-ranges"]);
  return params;
}

function leadRecords(matches, filter, previous = []) {
  const seen = new Set(previous.map((lead) => lead.email));
  const leads = previous.slice();
  const drops = { no_email: 0, email_status: 0, duplicate_email: 0 };
  for (const person of matches) {
    const lead = toLeadRecord(person);
    if (!lead) { drops.no_email++; continue; }
    if (filter.length && !filter.includes(lead.email_status)) { drops.email_status++; continue; }
    if (seen.has(lead.email)) { drops.duplicate_email++; continue; }
    seen.add(lead.email);
    leads.push(lead);
  }
  return { leads, drops };
}

async function run(mode, argv = process.argv) {
  const args = parseArgs(argv);
  const envFile = args["env-file"] ? path.resolve(args["env-file"]) : null;
  const os = getOsConfig({ ...(envFile ? readEnvFile(envFile) : {}), ...process.env });
  if (os.missing.length) throw new Error(`${os.missing.join(" and ")} not set. Export them or pass --env-file.`);
  const timeBudgetMs = positiveInteger(args["time-budget-ms"], 90000, "--time-budget-ms");
  const client = new ApolloClient({ osUrl: os.osUrl, osApiKey: os.osApiKey,
    connectionEnvFile: envFile, timeBudgetMs, verbose: !!args.verbose });
  const output = args.output ? path.resolve(args.output) : null;
  let filter = parseList(args["email-status-filter"] === undefined ? "verified,likely" : args["email-status-filter"]);
  let result;
  const checkpoint = () => { if (output) writeJson(output, result); };
  const emit = () => {
    checkpoint();
    if (!output) console.log(JSON.stringify(result, null, 2));
    console.error(`${mode}: ${result.meta.complete ? "complete" : "incomplete"} (${result.meta.stop_reason}); ` +
      `${result.leads?.length ?? result.people?.length ?? 0} records${output ? ` saved to ${output}` : ""}`);
    return result.meta.complete ? 0 : 2;
  };
  const baseMeta = { source: "apollo", complete: false, stop_reason: "in_progress", not_enriched: 0,
    not_enriched_people: [], enriched: 0, enriched_count: 0, processed_count: 0, leads_with_email: 0,
    email_status_filter: filter, drops: { no_email: 0, email_status: 0, duplicate_email: 0 } };
  let people;
  let previousLeads = [];
  let previousMatched = 0;
  let previousProcessed = 0;
  let previousDrops = baseMeta.drops;

  if (mode === "enrich") {
    if (!args.input) throw new Error("--input is required (JSON people list or partial Apollo result)");
    const raw = readJson(path.resolve(args.input));
    if (raw === null) throw new Error(`Input file not found: ${args.input}`);
    const resume = raw?.meta?.source === "apollo" && Array.isArray(raw.meta.not_enriched_people) && Array.isArray(raw.leads);
    people = resume ? raw.meta.not_enriched_people : Array.isArray(raw) ? raw : raw.people || raw.leads;
    if (!Array.isArray(people)) throw new Error("Input must be an array or contain a people/leads array");
    people.forEach(toMatchDetails);
    if (resume) {
      previousLeads = raw.leads;
      previousMatched = raw.meta.enriched ?? raw.meta.enriched_count ?? 0;
      previousProcessed = raw.meta.processed_count || 0;
      previousDrops = raw.meta.drops || previousDrops;
      if (args["email-status-filter"] === undefined) filter = raw.meta.email_status_filter || filter;
      else if (raw.meta.email_status_filter && JSON.stringify([...filter].sort()) !== JSON.stringify([...raw.meta.email_status_filter].sort()))
        throw new Error("Keep the saved email-status-filter when resuming; earlier filtered matches are not available to re-filter");
    }
    result = { leads: previousLeads, meta: { ...(resume ? raw.meta : {}), ...baseMeta,
      enriched_at: isoNow(), input_count: previousProcessed + people.length,
      enriched: previousMatched, enriched_count: previousMatched, processed_count: previousProcessed,
      leads_with_email: previousLeads.length, drops: previousDrops, email_status_filter: filter,
      not_enriched: people.length, not_enriched_people: people,
      ...(raw.meta?.search_complete !== undefined ? { search_complete: raw.meta.search_complete,
        search_stop_reason: raw.meta.search_stop_reason, search_next_page: raw.meta.search_next_page } : {}) } };
    delete result.meta.error_status;
  } else {
    const params = searchParams(args);
    const maxResults = positiveInteger(args["max-results"], mode === "search" ? 50 : 100, "--max-results");
    const maxPages = Math.min(Math.ceil(maxResults / 100), 500);
    result = { ...(mode === "search" ? { people: [] } : { leads: [] }), meta: { ...baseMeta,
      searched_at: isoNow(), search_params: params, total_found: 0, max_results: maxResults,
      search_complete: false, search_stop_reason: "in_progress", search_next_page: 1 } };
    checkpoint();
    const searched = await client.searchAllPeople(params, { maxPages, maxResults, onProgress: (state) => {
      result.meta.total_found = state.people.length;
      result.meta.search_complete = state.complete;
      result.meta.search_stop_reason = state.stop_reason;
      result.meta.search_next_page = state.next_page;
      result.meta.complete = mode === "search" && state.complete;
      result.meta.stop_reason = state.stop_reason;
      if (state.error_status !== undefined) result.meta.error_status = state.error_status;
      if (mode === "search") result.people = state.people;
      else { result.meta.not_enriched = state.people.length; result.meta.not_enriched_people = state.people; }
      checkpoint();
    } });
    if (mode === "search") {
      result.meta.note = "Search records only; no enrichment was requested. Preview is a live quota-consuming operation.";
      return emit();
    }
    people = searched.people;
  }

  // Persist pending inputs before the first paid batch, including an empty run.
  checkpoint();
  await client.bulkEnrichAll(people, { batchDelayMs: 1200, onProgress: (state) => {
    const converted = leadRecords(state.matches, filter, previousLeads);
    result.leads = converted.leads;
    Object.assign(result.meta, {
      enriched: previousMatched + state.matches.length,
      enriched_count: previousMatched + state.matches.length,
      processed_count: previousProcessed + state.processed_count,
      leads_with_email: result.leads.length,
      not_enriched: state.not_enriched, not_enriched_people: state.not_enriched_people,
      complete: state.complete && result.meta.search_complete !== false,
      stop_reason: !state.complete ? state.stop_reason : result.meta.search_complete === false ? result.meta.search_stop_reason : "completed",
      drops: Object.fromEntries(Object.entries(converted.drops).map(([key, value]) => [key, value + (previousDrops[key] || 0)])),
    });
    if (state.error_status !== undefined) result.meta.error_status = state.error_status;
    checkpoint();
  } });
  return emit();
}

module.exports = { run, searchParams, leadRecords, positiveInteger };
