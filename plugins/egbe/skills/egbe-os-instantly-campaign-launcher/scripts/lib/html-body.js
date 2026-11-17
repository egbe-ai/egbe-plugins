// Plain-text email body -> the HTML Instantly sends. Shared by the campaign
// steps (launch-campaign.js) and the agent's replies (send-reply.js): an email
// sent as text only loses its line breaks in clients that show the HTML part.

function escapeHtml(s) {
  // Escape `"` and `'` too — bodies are wrapped in `<a href="...">` and could
  // otherwise be embedded in attribute context, where unescaped quotes break
  // out of the attribute and form a tiny XSS vector if a lead-supplied token
  // ever ends up rendered server-side. Cheap to escape, no downside.
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Append UTM tracking params to a URL so traffic from cold-email lands as
// (source=instantly, medium=email, campaign=<run_key>) in product analytics.
// per-run attribution including purchase signals via Stripe metadata.
//   - `utm_source=instantly`        — distinguishes cold email from organic / Reddit / ads
//   - `utm_medium=email`            — canonical medium for outbound email
//   - `utm_campaign=<run_key>`      — distinguishes runs of the same product
// Existing UTM values are replaced so live URLs match the immutable binding
// persisted in manifest.json and conclusion.json.
function addUtmTags(url, runKey) {
  if (!runKey || typeof url !== "string") return url;
  try {
    const parsed = new URL(url);
    parsed.searchParams.set("utm_source", "instantly");
    parsed.searchParams.set("utm_medium", "email");
    parsed.searchParams.set("utm_campaign", runKey);
    return parsed.toString();
  } catch {
    const hashIndex = url.indexOf("#");
    const base = hashIndex >= 0 ? url.slice(0, hashIndex) : url;
    const fragment = hashIndex >= 0 ? url.slice(hashIndex) : "";
    const sep = base.includes("?") ? "&" : "?";
    return `${base}${sep}utm_source=instantly&utm_medium=email&utm_campaign=${encodeURIComponent(runKey)}${fragment}`;
  }
}

// A body is HTML when it has a common tag, or any tag with its closing tag
// (`<section>…</section>`). Text that only contains `<your name>` or
// `costs < a coffee` is still plain text: it gets escaped and one <div> per
// line, not sent as-is.
const HTML_TAG =
  /<\/?(?:a|b|i|u|p|br|hr|div|span|font|strong|em|small|sub|sup|ul|ol|li|h[1-6]|blockquote|pre|code|table|thead|tbody|tr|td|th|img|center)\b[^<>]*>/i;
const PAIRED_TAG = /<([a-z][\w-]*)\b[^<>]*>[\s\S]*<\/\1\s*>/i;
// `[anchor](url)`; the URL may hold one level of balanced parentheses
// (`https://en.wikipedia.org/wiki/X_(Y)`).
const MARKDOWN_LINK = /\[([^\]\n]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)/g;
// Link targets that become anchors; anything else (`javascript:`, `data:`,
// a relative path) stays as text. A target without a scheme that reads as a
// domain (`rolloo.app`, `www.rolloo.app/start`) is taken as https. A file
// name (`report.pdf`, `settings.json`) is not a domain and stays text.
const LINK_SCHEME = /^(?:https?:\/\/|mailto:|tel:)/i;
const FILE_EXTENSION =
  /^(?:[a-z0-9-]+\.)+(?:pdf|json|csv|txt|png|jpe?g|gif|svg|webp|zip|docx?|xlsx?|pptx?|html?|m?js|ts)(?:[/?#]|$)/i;
const BARE_DOMAIN = /^(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/?#]\S*)?$/i;

function markdownTarget(url) {
  if (LINK_SCHEME.test(url)) return url;
  if (BARE_DOMAIN.test(url) && !FILE_EXTENSION.test(url)) return `https://${url}`;
  return null;
}
const WEB_URL = /^https?:\/\//i;
// \u0001/\u0002 delimit the markdown-link placeholders in plainToHtmlBody.
const BARE_URL = /https?:\/\/[^\s<>"\u0001\u0002]+/g;

// `see https://x.com/pricing.`, `(https://x.com/app)`, `**https://x.com**`:
// the sentence's punctuation and markdown emphasis are not part of the URL.
// `*` / `_` count as emphasis only when the same char sits right before the
// URL (`https://x.com/a_b_` keeps its `_`). A closing bracket stays when the
// URL opened one itself (`https://en.wikipedia.org/wiki/X_(Y)`).
function splitTrailingPunctuation(url, before = "") {
  let end = url.length;
  while (end > 0) {
    const ch = url[end - 1];
    const open = { ")": "(", "]": "[" }[ch];
    const head = url.slice(0, end);
    if (
      ".,;:!?'\u2026".includes(ch) ||
      ("*_".includes(ch) && ch === before) ||
      (open && head.split(ch).length > head.split(open).length)
    ) {
      end -= 1;
    } else {
      break;
    }
  }
  return [url.slice(0, end), url.slice(end)];
}

// A link left as written (another site's, `mailto:` / `tel:`, or not a
// parseable URL) may still hold `"`, `<` or `>`; percent-encode them so the href cannot break
// out of its attribute. URLs that went through `new URL()` have none.
function safeHref(url) {
  return String(url).replace(/["<>]/g, (ch) => encodeURIComponent(ch));
}

const bareHost = (host) => host.toLowerCase().replace(/^www\./, "");

function hostOf(url) {
  try {
    return bareHost(new URL(url).hostname);
  } catch {
    return null;
  }
}

// Only http(s) links get UTMs: `mailto:` / `tel:` stay as written.
// utmHosts (optional) limits UTMs to links on those hosts or their
// subdomains; other links are left as written, and an empty list tags none.
function utmTagger(runKey, utmHosts) {
  const hosts = utmHosts?.map(bareHost);
  return (url) => {
    if (!WEB_URL.test(url)) return url;
    if (hosts) {
      const host = hostOf(url);
      if (!host || !hosts.some((h) => host === h || host.endsWith(`.${h}`)))
        return url;
    }
    return addUtmTags(url, runKey);
  };
}

/**
 * Auto-convert a plain-text body (with `\n\n` paragraph breaks and bare URLs)
 * into HTML so Instantly delivers consistent rendering across email clients.
 *
 * Rules (Instantly editor-native markup — the CREATE endpoint rewrites
 * `<p>` blocks into margin-less `<div>`s, collapsing paragraph spacing in
 * the delivered mail, while PATCH keeps `<p>` verbatim; emitting the editor's
 * own format renders identically on both API paths):
 *   - every line → its own `<div>...</div>`
 *   - `\n\n` (blank line) → explicit `<div><br /></div>` separator
 *   - markdown links `[anchor](url)` → `<a href="url+UTMs">anchor</a>` so
 *     marketologist controls the visible CTA wording per product
 *     (e.g. `[try Rolloo free](https://rolloo.app/)`); only http(s),
 *     `mailto:` and `tel:` targets become links (`rolloo.app` without a
 *     scheme counts as https), and only http(s) get UTMs
 *   - bare http(s):// URLs → `<a href="url+UTMs">url</a>` (display = clean URL,
 *     UTMs hidden in href so the email body stays human-looking); trailing
 *     punctuation stays outside the link
 *   - merge tokens like `{{firstName}}` are preserved intact (HTML-safe by
 *     virtue of escaping happening before token substitution on Instantly's
 *     side; we never escape the braces themselves).
 *
 * Idempotent: if the body already contains HTML, preserve its markup while
 * reconciling HTTP(S) anchor hrefs to the canonical UTM tuple.
 *
 * `utmHosts` (optional): tag only links to these hosts, as for a reply that
 * may link to someone else's site; `[]` tags no link.
 * `plain`: the body is plain text even if it contains a tag (an agent's
 * reply), so it is always escaped and split into lines.
 */
function plainToHtmlBody(
  body,
  runKey,
  { utmHosts, plain } = {},
) {
  if (typeof body !== "string" || !body.trim()) return body;
  const tag = utmTagger(runKey, utmHosts);
  if (!plain && (HTML_TAG.test(body) || PAIRED_TAG.test(body))) {
    return body.replace(
      /(<a\b[^>]*\bhref\s*=\s*)(["'])(https?:\/\/[^"']+)\2/gi,
      (_, prefix, quote, url) => `${prefix}${quote}${tag(url)}${quote}`,
    );
  }

  // Two-pass extraction so escapeHtml doesn't corrupt the link markup.
  // Pass 1: pull markdown links out of body, replace with sentinels we can
  //         reinsert AFTER escapeHtml runs (so the anchor + href bypass
  //         escaping). The sentinels are wrapped in the control chars
  //         \u0001/\u0002, which email text does not contain; BARE_URL
  //         stops at them, so a URL right before a markdown link ends there.
  // CRLF / CR line ends count as \n: blank lines collapse the same way and
  // no stray \r ends up inside a <div>.
  body = body.replace(/\r\n?/g, "\n");
  const linkRegistry = [];
  const SENTINEL_OPEN = "\u0001OCLINK\u0001";
  const SENTINEL_CLOSE = "\u0002OCLINK\u0002";
  const withSentinels = body.replace(MARKDOWN_LINK, (match, anchor, target) => {
    const url = markdownTarget(target);
    if (!url) return match;
    const idx = linkRegistry.length;
    linkRegistry.push({ url: tag(url), anchor });
    return `${SENTINEL_OPEN}${idx}${SENTINEL_CLOSE}`;
  });

  // Pass 2: paragraphs + escapeHtml + raw-URL linkify (bare URLs stay
  // displayed as the clean original URL but href carries UTMs). URLs are
  // cut out of the raw line before escaping: escaped first, `?a=1&b=2`
  // reaches addUtmTags as `&amp;b=2` and the product loses the parameter.
  const linkifyBare = (line) => {
    let out = "";
    let last = 0;
    for (const m of line.matchAll(BARE_URL)) {
      const [url, trailing] = splitTrailingPunctuation(
        m[0],
        line[m.index - 1],
      );
      out +=
        escapeHtml(line.slice(last, m.index)) +
        `<a href="${safeHref(tag(url))}">${escapeHtml(url)}</a>` +
        escapeHtml(trailing);
      last = m.index + m[0].length;
    }
    return out + escapeHtml(line.slice(last));
  };

  const lines = withSentinels
    .replace(/^\n+/, "")
    .replace(/\n+$/, "")
    .replace(/\n{2,}/g, "\n\n")
    .split("\n");
  const rendered = lines
    .map((line) => {
      if (line.trim() === "") return "<div><br /></div>";
      return `<div>${linkifyBare(line)}</div>`;
    })
    .join("");

  // Pass 3: substitute markdown-link sentinels back in. escapeHtml leaves
  // SENTINEL_OPEN/CLOSE as they are (control chars pass through), so the
  // regex still matches.
  return rendered.replace(
    new RegExp(`${SENTINEL_OPEN}(\\d+)${SENTINEL_CLOSE}`, "g"),
    (_, idx) => {
      const entry = linkRegistry[Number(idx)];
      if (!entry) return "";
      return `<a href="${safeHref(entry.url)}">${escapeHtml(entry.anchor)}</a>`;
    },
  );
}

// The text part of the same email: `[anchor](url)` reads as `anchor (url)`
// in clients that show only text. Same targets as the html part; other
// markdown stays as written there too.
function markdownLinksToText(body) {
  if (typeof body !== "string") return body;
  return body.replace(MARKDOWN_LINK, (match, anchor, target) => {
    const url = markdownTarget(target);
    if (!url) return match;
    return anchor === target || anchor === url ? url : `${anchor} (${url})`;
  });
}

// The first link (bare URL or markdown) in a plain-text body, or null.
function firstLink(body) {
  const text = String(body || "");
  return (text.match(BARE_URL) || text.match(MARKDOWN_LINK) || [null])[0];
}

// Hosts (without `www.`) of every link in a plain-text body.
function linkHosts(body) {
  const urls = [];
  for (const m of String(body || "").matchAll(MARKDOWN_LINK))
    urls.push(markdownTarget(m[2]));
  for (const m of String(body || "").matchAll(BARE_URL))
    urls.push(splitTrailingPunctuation(m[0], m.input[m.index - 1])[0]);
  return [...new Set(urls.filter(Boolean).map(hostOf).filter(Boolean))];
}

module.exports = {
  escapeHtml,
  addUtmTags,
  plainToHtmlBody,
  markdownLinksToText,
  firstLink,
  linkHosts,
};
