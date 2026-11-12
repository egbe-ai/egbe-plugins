const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function readJson(file, fallback = null) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, data) {
  ensureDir(path.dirname(file));
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((k) => JSON.stringify(k) + ":" + stableStringify(value[k]))
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function normalizeEmail(email) {
  return String(email || "")
    .trim()
    .toLowerCase();
}

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith("--")) continue;
    const key = arg.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      out[key] = true;
    } else {
      out[key] = next;
      i += 1;
    }
  }
  return out;
}

function isoNow() {
  return new Date().toISOString();
}

function ymd(date = new Date()) {
  return date.toISOString().slice(0, 10);
}

function slugify(value, max = 48) {
  return (
    String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, max) || "na"
  );
}

function titleCase(value) {
  return String(value || "")
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

function isGenericMailbox(email) {
  const local = normalizeEmail(email).split("@")[0] || "";
  return [
    "team",
    "hello",
    "info",
    "contact",
    "support",
    "sales",
    "admin",
    "ops",
    "office",
    "growth",
    "founders",
    "mail",
    "hi",
  ].includes(local);
}

function deriveSenderName({ firstName, lastName }) {
  const explicit = [firstName, lastName].filter(Boolean).join(" ").trim();
  // A mailbox local part is not evidence of a person's identity.
  return explicit || null;
}

function replaceSenderNameToken(text, senderName) {
  return String(text || "").replace(/{{\s*senderName\s*}}/g, senderName || "");
}

// Fields the Instantly /leads/add payload consumes directly. Anything else a
// sourcing script writes into a lead object is forwarded as a custom variable
// so copy tokens like {{personalization}} actually resolve — the import used
// to drop every non-standard field silently.
// Native Instantly lead fields the /leads/add payload accepts beyond the
// five always-sent ones — pass them through as-is instead of demoting them
// into custom_variables.
const NATIVE_OPTIONAL_LEAD_FIELDS = [
  "phone",
  "job_title",
  "lt_interest_status",
  "pl_value_lead",
  "assigned_to",
];

const RESERVED_LEAD_FIELDS = new Set([
  "email",
  "firstName",
  "first_name",
  "lastName",
  "last_name",
  "companyName",
  "company_name",
  "website",
  "personalization",
  "custom_variables",
  // Launcher-only overrides for the lead-name preflight; never sent to Instantly.
  "first_name_confirmed",
  "company_name_confirmed",
  ...NATIVE_OPTIONAL_LEAD_FIELDS,
]);
const MAX_CUSTOM_VARIABLE_LENGTH = 1000;

function buildImportLead(lead) {
  const importLead = {
    email: lead.email,
    first_name: lead.firstName || lead.first_name || "",
    last_name: lead.lastName || lead.last_name || "",
    company_name: lead.companyName || lead.company_name || "",
    website: lead.website || "",
  };
  if (lead.personalization != null && String(lead.personalization).trim()) {
    importLead.personalization = String(lead.personalization);
  }
  for (const key of NATIVE_OPTIONAL_LEAD_FIELDS) {
    if (lead[key] != null && lead[key] !== "") importLead[key] = lead[key];
  }
  // Idempotent: carry-over leads round-trip through this function (launch
  // stores its output, replenish re-applies it), so an already-built
  // custom_variables object must survive a second pass. Booleans are valid
  // Instantly custom values; the length cap only guards string blobs.
  const isImportableScalar = (value) =>
    typeof value === "string"
      ? value.length <= MAX_CUSTOM_VARIABLE_LENGTH
      : typeof value === "number" || typeof value === "boolean";
  const inherited =
    lead.custom_variables && typeof lead.custom_variables === "object"
      ? Object.entries(lead.custom_variables)
      : [];
  const customEntries = [...inherited, ...Object.entries(lead)].filter(
    ([key, value]) => !RESERVED_LEAD_FIELDS.has(key) && isImportableScalar(value),
  );
  if (customEntries.length) {
    importLead.custom_variables = Object.fromEntries(customEntries);
  }
  return importLead;
}

// Lead-name preflight. Lead sources (Apollo) sometimes put a title or
// credential in first_name ("CA" for Chartered Accountant) or return company
// names in ALL CAPS; templated into {{firstName}} / {{companyName}} that ships
// "Dear CA," to a real prospect. Exact, case-insensitive matches only (a
// trailing "." is ignored) — "Sheikh" is a real name part and is NOT listed.
const FIRST_NAME_TITLE_TOKENS = new Set([
  "ca", "cs", "cpa", "cma", "acca", "aca", "fca", "cfa",
  "mr", "mrs", "ms", "miss", "dr", "eng", "engr", "prof", "sir", "madam",
]);
const MAX_COMPANY_NAME_LENGTH = 60;

function letterCount(value) {
  return (String(value).match(/\p{L}/gu) || []).length;
}

// Has cased letters and none of them are lower case. Scripts without case
// (Arabic, CJK) are never "all caps".
function isAllCaps(value) {
  return /\p{Lu}/u.test(value) && !/\p{Ll}/u.test(value);
}

/** Why a lead's first name would render badly in {{firstName}}, or null. */
function firstNameProblem(lead) {
  if (lead?.first_name_confirmed === true) return null;
  const value = String(lead?.firstName || lead?.first_name || "").trim();
  if (!value) return "empty";
  if (FIRST_NAME_TITLE_TOKENS.has(value.replace(/\.+$/, "").toLowerCase())) {
    return "a title or credential, not a first name";
  }
  // Mixed-case short names are real (Li, Wu, Ng, Al, Jo, Ed); a single
  // letter or two capitals (CA, MR, AB) are initials or a credential.
  const letters = letterCount(value);
  if (letters <= 1) return "a single letter (an initial?)";
  if (letters === 2 && isAllCaps(value)) return "two capital letters (initials or a credential?)";
  if (isAllCaps(value)) return "ALL CAPS";
  return null;
}

/** Why a lead's company name would render badly in {{companyName}}, or null. */
function companyNameProblem(lead) {
  if (lead?.company_name_confirmed === true) return null;
  const value = String(lead?.companyName || lead?.company_name || "").trim();
  if (!value) return "empty";
  if (value.length > MAX_COMPANY_NAME_LENGTH) {
    return `${value.length} characters (limit ${MAX_COMPANY_NAME_LENGTH})`;
  }
  // A single short acronym (IBM, KPMG, BDO) is written in capitals on purpose.
  const shortAcronym = !/\s/.test(value) && letterCount(value) <= 4;
  if (isAllCaps(value) && !shortAcronym) return "ALL CAPS";
  return null;
}

/**
 * Which lead-name checks the copy needs: first names only when a step's
 * subject or body uses {{firstName}}, company names only for {{companyName}}.
 * Shared by the launcher preflight and replenishment.
 */
function leadNameChecksForSteps(steps) {
  const copy = (Array.isArray(steps) ? steps : [])
    .map((step) => `${step?.subject || ""}\n${step?.body || ""}`)
    .join("\n");
  return {
    checkFirstName: /{{\s*firstName\s*}}/.test(copy),
    checkCompanyName: /{{\s*companyName\s*}}/.test(copy),
  };
}

function findLeadVariableProblems(steps, leads, { skipEmails = null } = {}) {
  const copy = (steps || []).map(step => `${step.subject || ""}\n${step.body || ""}`).join("\n");
  const tokens = new Set([...copy.matchAll(/{{\s*([\w]+)\s*}}/g)].map(match => match[1]));
  tokens.delete("senderName"); // resolved once from authored/verified sender identity
  const aliases = { firstName: "first_name", lastName: "last_name", companyName: "company_name" };
  const problems = [];
  for (const lead of leads || []) {
    const email = normalizeEmail(lead?.email);
    if (!email || skipEmails?.has(email)) continue;
    const imported = buildImportLead(lead);
    for (const token of tokens) {
      const field = aliases[token] || token;
      const value = imported[field] ?? imported.custom_variables?.[token];
      if (value == null || String(value).trim() === "" || /{{.*}}/.test(String(value)))
        problems.push({ email, field: token, severity: "error", problem: "missing or unresolved substitution" });
      else if (field === "first_name" && lead.first_name_confirmed !== true &&
               FIRST_NAME_TITLE_TOKENS.has(String(value).trim().replace(/\.+$/, "").toLowerCase()))
        problems.push({ email, field: token, severity: "error", problem: "title or credential is not a confirmed recipient name" });
    }
  }
  return problems;
}

/**
 * Every lead (with an email) whose name fields would render badly in the
 * copy: first names only when the copy uses {{firstName}}, company names only
 * when it uses {{companyName}}. Leads in skipEmails (already imported) are
 * not checked. Returns [{ email, field, value, problem }].
 */
function findLeadNameProblems(
  leads,
  { checkFirstName = true, checkCompanyName = false, skipEmails = null } = {},
) {
  const problems = [];
  const seen = new Set();
  for (const lead of Array.isArray(leads) ? leads : []) {
    const email = normalizeEmail(lead?.email);
    if (!email || seen.has(email)) continue;
    seen.add(email);
    if (skipEmails && skipEmails.has(email)) continue;
    const firstProblem = checkFirstName ? firstNameProblem(lead) : null;
    if (firstProblem) {
      problems.push({
        email,
        field: "first_name",
        value: String(lead.firstName || lead.first_name || ""),
        problem: firstProblem,
        severity: firstProblem === "empty" || firstProblem === "a title or credential, not a first name" ? "error" : "warning",
      });
    }
    const companyProblem = checkCompanyName ? companyNameProblem(lead) : null;
    if (companyProblem) {
      problems.push({
        email,
        field: "company_name",
        value: String(lead.companyName || lead.company_name || ""),
        problem: companyProblem,
        severity: companyProblem === "empty" ? "error" : "warning",
      });
    }
  }
  return problems;
}

function readEnvFile(file) {
  const env = {};
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    if (!line || /^\s*#/.test(line)) continue;
    const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
    if (!match) continue;
    let [, key, value] = match;
    value = value.replace(/^['"]|['"]$/g, "");
    env[key] = value;
  }
  return env;
}

function resolveRunEnvFile(runDir, explicitEnvFile = null) {
  if (!runDir) return null;
  const envFile = explicitEnvFile
    ? path.resolve(explicitEnvFile)
    : path.join(runDir, ".env");
  return fs.existsSync(envFile) ? envFile : null;
}

function loadRunEnv(runDir, explicitEnvFile = null) {
  if (!runDir) return null;
  const envFile = resolveRunEnvFile(runDir, explicitEnvFile);
  if (!envFile) return null;
  const env = readEnvFile(envFile);
  for (const [key, value] of Object.entries(env)) {
    if (!(key in process.env)) process.env[key] = value;
  }
  return envFile;
}

function getOsConfig(env = process.env) {
  const osApiKey = String(env.OS_API_KEY || "").trim();
  const osUrl = String(env.OS_URL || "")
    .trim()
    .replace(/\/$/, "");
  const missing = [];
  if (!osUrl) missing.push("OS_URL");
  if (!osApiKey) missing.push("OS_API_KEY");
  return { osUrl, osApiKey, missing };
}

/**
 * Make sure the run-scoped `.env` file contains OS credentials.
 * If the file is missing or doesn't have them, copy from `process.env`.
 * Cron jobs run with their own environment and only see what's in `--env-file`,
 * so persisting container-level OS creds into the run `.env` is required
 * for monitor / reply / replenish / conclude to work post-launch.
 *
 * Returns: { envFilePath, source: 'existing'|'created'|'updated', wrote: string[] }
 */
function ensureRunEnv(runDir, explicitEnvFile = null) {
  if (!runDir) throw new Error("ensureRunEnv requires runDir");
  // An explicit file supplies credentials, but identity snapshots always
  // belong to the private run file, never a shared workspace credential file.
  const envFile = path.resolve(runDir, ".env");
  const sourceFile = explicitEnvFile ? path.resolve(explicitEnvFile) : envFile;

  ensureDir(path.dirname(envFile));
  const exists = fs.existsSync(envFile);
  const existing = fs.existsSync(sourceFile) ? readEnvFile(sourceFile) : {};

  const required = ["OS_URL", "OS_API_KEY"];
  const optional = [];
  const wrote = [];
  const next = { ...existing };

  for (const key of [...required, ...optional]) {
    if (!next[key] && process.env[key]) {
      next[key] = String(process.env[key]).trim();
      wrote.push(key);
    }
  }

  // Prefer a validated current workspace during interactive launch/install.
  // Outside an active workspace, explicit saved identity settings can be reused.
  // Scheduled workers only load the resulting snapshot and do not refresh it.
  let headers = {};
  const adapter = path.join(__dirname, "connection-identity.js");
  if (next.OS_URL && fs.existsSync(adapter)) {
    const connectionHeaders = require(adapter);
    headers = connectionHeaders(next.OS_URL);
    const relativeRun = path.relative(process.cwd(), path.resolve(runDir));
    const runInWorkspace = !path.isAbsolute(relativeRun) && relativeRun !== ".." && !relativeRun.startsWith(".." + path.sep);
    // Even an unknown caller is interactive when running inside this run's
    // workspace. An unrelated scheduler directory must not supply its identity.
    const activeWorkspace = fs.existsSync(path.join(process.cwd(), ".env.local")) && (process.env.OS_AGENT_NAME || runInWorkspace);
    if (explicitEnvFile && !headers["X-Egbe-Connection-Id"] && !activeWorkspace) {
      headers = connectionHeaders(next.OS_URL, sourceFile);
    }
  }
  if (headers["X-Egbe-Connection-Id"] && headers["X-Egbe-Agent-Name"]) {
    const agent = headers["X-Egbe-Agent-Name"];
    const slug = agent.toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    const identity = { OS_AGENT_NAME: agent, ["OS_CONNECTION_ID_" + slug]: headers["X-Egbe-Connection-Id"] };
    if (headers["X-Egbe-Workspace-Name"]) identity.OS_WORKSPACE_NAME = headers["X-Egbe-Workspace-Name"];
    else if ("OS_WORKSPACE_NAME" in next) { delete next.OS_WORKSPACE_NAME; wrote.push("OS_WORKSPACE_NAME"); }
    for (const [key, value] of Object.entries(identity)) {
      if (next[key] !== value) { next[key] = value; wrote.push(key); }
    }
  } else if (next.OS_AGENT_NAME || Object.keys(next).some(key => key.startsWith("OS_CONNECTION_ID_"))) {
    // An explicit empty selection prevents both prior-agent attribution and
    // shell-name fallback. Keep saved UUIDs without selecting any of them.
    if (next.OS_AGENT_NAME !== "") { next.OS_AGENT_NAME = ""; wrote.push("OS_AGENT_NAME"); }
  }

  // Required-but-still-missing -> caller will fail downstream via getOsConfig.
  // We still write what we have so cron jobs see whatever the container exported.

  if (!exists || wrote.length > 0 || explicitEnvFile) {
    const lines = Object.entries(next).map(([k, v]) => {
      const safe = String(v).replace(/\r?\n/g, " ");
      return `${k}=${["OS_AGENT_NAME", "OS_WORKSPACE_NAME"].includes(k) ? JSON.stringify(safe) : safe}`;
    });
    fs.writeFileSync(envFile, lines.join("\n") + "\n", { mode: 0o600 });
  }
  // Always enforce 0o600 even on pre-existing files; cron install validates this.
  try {
    fs.chmodSync(envFile, 0o600);
  } catch (err) {
    console.error(
      `WARNING: chmod 600 ${envFile} failed (${err.code || err.message}). ` +
        `Cron install will refuse to run with permissions wider than 0o600. ` +
        `Fix the filesystem permissions manually before re-running install-crons.`,
    );
  }

  // Reflect into process.env so the current process can see what we just wrote.
  for (const [k, v] of Object.entries(next)) {
    if (!(k in process.env)) process.env[k] = v;
  }

  return {
    envFilePath: envFile,
    source: exists ? (wrote.length || explicitEnvFile ? "updated" : "existing") : "created",
    wrote,
  };
}

function addTagRecord(value, tags) {
  if (value == null) return;
  if (Array.isArray(value)) {
    value.forEach((item) => addTagRecord(item, tags));
    return;
  }
  if (typeof value === "object") {
    for (const key of ["id", "tag_id", "custom_tag_id"]) {
      if (value[key] != null) tags.ids.add(String(value[key]));
    }
    for (const key of ["label", "name", "tag_label"]) {
      if (value[key]) tags.labels.add(String(value[key]));
    }
    return;
  }
  tags.ids.add(String(value));
}

function collectCampaignTags(resource) {
  const tags = { ids: new Set(), labels: new Set() };
  if (!resource || typeof resource !== "object") return tags;

  for (const key of ["custom_tags", "tags"]) {
    addTagRecord(resource[key], tags);
  }
  for (const key of ["custom_tag_ids", "tag_ids"]) {
    addTagRecord(resource[key], tags);
  }
  for (const key of ["custom_tag_labels", "tag_labels"]) {
    const value = resource[key];
    if (Array.isArray(value))
      value.forEach((label) => label && tags.labels.add(String(label)));
  }
  return tags;
}

function campaignOwnershipStatus(resource, ownership) {
  if (!resource || !ownership) return "unknown";
  const tags = collectCampaignTags(resource);
  if (!tags.ids.size && !tags.labels.size) return "unknown";

  const runMatch =
    (ownership.run_tag_id != null &&
      tags.ids.has(String(ownership.run_tag_id))) ||
    (ownership.run_tag_label &&
      tags.labels.has(String(ownership.run_tag_label)));
  const agentMatch =
    (ownership.agent_tag_id != null &&
      tags.ids.has(String(ownership.agent_tag_id))) ||
    (ownership.agent_tag_label &&
      tags.labels.has(String(ownership.agent_tag_label)));

  if (runMatch && agentMatch) return "owned";
  if (runMatch || agentMatch) return "unknown";
  return "foreign";
}

function assertCampaignNotForeign(resource, ownership, context = "campaign") {
  const status = campaignOwnershipStatus(resource, ownership);
  if (status === "foreign") {
    throw new Error(`${context} exists but is not owned by this run`);
  }
  return status;
}

module.exports = {
  ensureDir,
  readJson,
  writeJson,
  sha256,
  stableStringify,
  normalizeEmail,
  parseArgs,
  isoNow,
  ymd,
  slugify,
  titleCase,
  isGenericMailbox,
  deriveSenderName,
  replaceSenderNameToken,
  buildImportLead,
  firstNameProblem,
  companyNameProblem,
  findLeadNameProblems,
  leadNameChecksForSteps,
  findLeadVariableProblems,
  MAX_COMPANY_NAME_LENGTH,
  readEnvFile,
  resolveRunEnvFile,
  loadRunEnv,
  ensureRunEnv,
  getOsConfig,
  campaignOwnershipStatus,
  assertCampaignNotForeign,
};
