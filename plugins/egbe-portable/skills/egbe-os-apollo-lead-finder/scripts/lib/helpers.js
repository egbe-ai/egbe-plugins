const fs = require('fs');
const path = require('path');

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function readJson(file, fallback = null) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJson(file, data) {
  ensureDir(path.dirname(file));
  const temporary = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temporary, JSON.stringify(data, null, 2) + '\n');
  fs.renameSync(temporary, file);
}

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith('--')) continue;
    const key = arg.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith('--')) {
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

function normalizeEmail(email) {
  return String(email || '').trim().toLowerCase();
}

/**
 * Convert Apollo person + enrichment data into a lead object
 * compatible with Instantly campaign launcher.
 */
function toLeadRecord(person) {
  if (!person) return null;
  const email = normalizeEmail(person.email);
  if (!email) return null;
  return {
    email,
    first_name: person.first_name || '',
    last_name: person.last_name || '',
    company_name: person.organization?.name || '',
    website: person.organization?.primary_domain || person.organization?.website_url || '',
    // Extended fields (ignored by Instantly, useful for analytics)
    title: person.title || '',
    seniority: person.seniority || '',
    linkedin_url: person.linkedin_url || '',
    city: person.city || '',
    state: person.state || '',
    country: person.country || '',
    industry: person.organization?.industry || '',
    company_size: person.organization?.estimated_num_employees || null,
    email_status: person.email_status || '',
    apollo_id: person.id || '',
  };
}

/**
 * Parse comma- or semicolon-separated string into an array.
 * Returns empty array for falsy input.
 */
function parseList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return String(value).split(/[,;]+/).map(s => s.trim()).filter(Boolean);
}

/**
 * Parse semicolon-separated string into an array.
 * Use for values that contain commas internally (e.g. employee ranges "11,50;51,200").
 */
function parseSemicolonList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return String(value).split(/;+/).map(s => s.trim()).filter(Boolean);
}

function readEnvFile(file) {
  const env = {};
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    if (!line || /^\s*#/.test(line)) continue;
    const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
    if (!match) continue;
    let [, key, value] = match;
    value = value.replace(/^['"]|['"]$/g, '');
    env[key] = value;
  }
  return env;
}

function getOsConfig(env = process.env) {
  const osUrl = String(env.OS_URL || '').trim().replace(/\/$/, '');
  const osApiKey = String(env.OS_API_KEY || '').trim();
  const missing = [];
  if (!osUrl) missing.push('OS_URL');
  if (!osApiKey) missing.push('OS_API_KEY');
  return { osUrl, osApiKey, missing };
}

module.exports = {
  ensureDir,
  readJson,
  writeJson,
  parseArgs,
  isoNow,
  normalizeEmail,
  toLeadRecord,
  parseList,
  parseSemicolonList,
  readEnvFile,
  getOsConfig,
};
