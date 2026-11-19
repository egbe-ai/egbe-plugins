"use strict";

/**
 * places-filters — email and owner-name filter data for places-leads.js.
 *
 * Scraping small-business sites surfaces addresses that are NOT the business:
 * font-license attribution embedded by DIY site builders, error-tracking and
 * hosting infrastructure, asset filenames that look like emails, and no-reply
 * senders. These lists keep them out of a leads file.
 */

const { normalizeEmail } = require("./helpers");

// Exact-match blocklist. Font authors are credited inside font metadata /
// license text that site builders inline into pages, so their personal
// addresses appear on thousands of unrelated small-business sites.
const TRAP_EMAILS = [
  "impallari@gmail.com", // Pablo Impallari (Impallari Type) — Google Fonts metadata
];

// Pattern blocklist: asset artifacts and infrastructure addresses.
const TRAP_EMAIL_PATTERNS = [
  // Asset filename artifacts, e.g. "logo.svg@..." (local part ends in an
  // asset extension) or "...@2x.png" (domain part ends in one).
  /\.(png|jpe?g|gif|svg|webp|js|css)@/i,
  /\.(png|jpe?g|gif|svg|webp|js|css)$/i,
  // Error tracking / site-builder / hosting infrastructure, including
  // subdomains such as sentry-next.wixpress.com.
  /@([a-z0-9-]+\.)*sentry\.io$/i,
  /@([a-z0-9-]+\.)*wixpress\.com$/i,
  /@([a-z0-9-]+\.)*example\.com$/i,
  /@([a-z0-9-]+\.)*godaddy\.com$/i,
  // Unattended senders.
  /^(no-?reply|donotreply)@/i,
];

// Role-address heuristic. The caller selects whether to prefer these;
// earlier entries rank higher among generics, not as a validity judgment.
const GENERIC_LOCAL_PARTS = [
  "info",
  "contact",
  "hello",
  "office",
  "admin",
  "support",
  "bookings",
  "sales",
  "mail",
  "team",
];

// Words that look like capitalized first names in page copy but are not
// people: business-entity words, role words, and common city/brand tokens
// seen in local-services business names.
// Freemail-domain heuristic used by the default ranking. It does not prove
// the address belongs to the listed business or a particular person.
const FREEMAIL_DOMAINS = new Set([
  "gmail.com",
  "yahoo.com",
  "outlook.com",
  "hotmail.com",
  "icloud.com",
  "me.com",
  "aol.com",
  "live.com",
  "msn.com",
  "comcast.net",
  "att.net",
  "sbcglobal.net",
  "verizon.net",
]);

const NON_NAME_WORDS = [
  // Pronouns / heading tokens captured by owner-intro patterns
  // ("Meet Our Team", "Meet Your Photographer", "I'm Ready To Book")
  "our",
  "your",
  "us",
  "me",
  "my",
  "here",
  "ready",
  // Business / entity words
  "team",
  "studio",
  "photography",
  "photo",
  "media",
  "group",
  "llc",
  "inc",
  "realty",
  "properties",
  "the",
  "info",
  "admin",
  "sales",
  "support",
  "contact",
  "office",
  "hello",
  // Brand-ish tokens common in local-services names
  "pro",
  "pros",
  "prime",
  "elite",
  "best",
  "top",
  "real",
  "estate",
  "home",
  "homes",
  "house",
  "imaging",
  "images",
  "drone",
  "aerial",
  "virtual",
  "staging",
  "tours",
  "design",
  // Obvious city tokens (large US metros show up in business names)
  "austin",
  "dallas",
  "houston",
  "phoenix",
  "denver",
  "atlanta",
  "chicago",
  "seattle",
  "miami",
  "orlando",
  "tampa",
  "vegas",
  "boston",
  "portland",
  "nashville",
  "charlotte",
];

// Conservative shape check — one @, a dot in the domain, no whitespace.
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * True when the email is a known trap: an exact blocklist hit or any
 * asset/infrastructure pattern match.
 */
function isTrapEmail(email) {
  const e = normalizeEmail(email);
  if (!e) return false;
  if (TRAP_EMAILS.includes(e)) return true;
  return TRAP_EMAIL_PATTERNS.some((re) => re.test(e));
}

/**
 * Classify an email candidate:
 *   'trap'     — blocklisted, artifact-shaped, or malformed (never emit)
 *   'generic'  — role-address-looking local part (info@, contact@, ...)
 *   'personal' — other shape; not proof of a personal mailbox
 */
function classifyEmail(email) {
  const e = normalizeEmail(email);
  if (!e || !EMAIL_SHAPE.test(e)) return "trap";
  if (isTrapEmail(e)) return "trap";
  const local = e.split("@")[0];
  if (GENERIC_LOCAL_PARTS.includes(local)) return "generic";
  return "personal";
}

// Phrases owners use to introduce themselves on their own sites. Each
// pattern captures one capitalized word right after the phrase. The phrase
// part tolerates sentence-case; the captured name must stay capitalized, so
// no `i` flag (it would loosen the [A-Z][a-z]+ capture too).
const OWNER_NAME_PATTERNS = [
  /\b[Mm]y name is\s+([A-Z][a-z]+)\b/,
  /\bI\s*(?:'|’)?m\s+([A-Z][a-z]+)\b/,
  /\bI am\s+([A-Z][a-z]+)\b/,
  /\b(?:[Ff]ounded|[Oo]wned|[Rr]un|[Oo]perated)\s+[Bb]y\s+([A-Z][a-z]+)\b/,
  /\b(?:[Oo]wner|[Ff]ounder|[Pp]hotographer)\s*[:,]\s*([A-Z][a-z]+)\b/,
  /\b[Mm]eet\s+([A-Z][a-z]+)\b/,
];

/**
 * Suggest an unverified name candidate from English page text.
 *
 * Returns a capitalized first name only when the candidate is not in
 * NON_NAME_WORDS and does not appear inside the business name (a word
 * shared with the business name is far more likely a brand/city token
 * than a person). Returns '' when no candidate passes these heuristics.
 */
function extractOwnerFirstName(text, businessName) {
  const haystack = String(text || "");
  if (!haystack) return "";
  const businessWords = new Set(
    String(businessName || "")
      .toLowerCase()
      .split(/[^a-z]+/)
      .filter(Boolean),
  );
  for (const pattern of OWNER_NAME_PATTERNS) {
    const match = haystack.match(pattern);
    if (!match) continue;
    const candidate = match[1];
    const lower = candidate.toLowerCase();
    if (NON_NAME_WORDS.includes(lower)) continue;
    if (businessWords.has(lower)) continue;
    return candidate[0].toUpperCase() + candidate.slice(1).toLowerCase();
  }
  return "";
}

module.exports = {
  GENERIC_LOCAL_PARTS,
  FREEMAIL_DOMAINS,
  classifyEmail,
  extractOwnerFirstName,
};
