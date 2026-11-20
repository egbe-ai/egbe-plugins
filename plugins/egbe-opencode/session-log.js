// Egbe session logging for OpenCode.
//
// On by default in a project folder set up for Egbe, as the plugin's README and
// Egbe's setup disclose. When a session goes idle after a run, it sends that
// run's turn (the founder's message, model calls with usage, tool calls with
// their results, and the reply) as OTLP traces to Egbe's telemetry gateway, the
// same `/ingest/opencode` route the Langfuse OpenCode plugin would use,
// authenticated with the project's own Egbe key and grouped into the OpenCode
// session. It stays off when the project has no private .env.local with Egbe
// credentials, when that file says EGBE_SESSION_LOGGING=off, when the project's
// saved choice declines logging or stops the opencode collector, when the
// plugin's `sessionLogging` option is false, or when the Langfuse OpenCode plugin
// already sends this project's sessions to Egbe. It never fails a run: errors are
// recorded and the turn is skipped.
import { randomBytes } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import path from "node:path";

export const OS_URL = "https://os.hz.egbe.dev";
export const GATEWAY = "https://observe.hz.egbe.dev/telemetry";
export const HARNESS = "opencode";
const MAX_TEXT = 16_000;
const MAX_BODY = 7 * 1024 * 1024;

function readEnv(file) {
  // Only the project's private settings count: setup writes .env.local with
  // mode 600, while a copy that came with a cloned repository is readable by others.
  const stat = statSync(file);
  if (process.platform !== "win32" && (stat.mode & 0o077) !== 0) return undefined;
  const values = {};
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const match = /^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)=(.*)$/.exec(line);
    if (match) values[match[1]] = match[2].trim().replace(/^"(.*)"$/, "$1").replace(/^'(.*)'$/, "$1");
  }
  return values;
}

// The collector's own "enabled": false or "stop", or a declined or skipped consent.
function savedChoiceDeclines(folder) {
  let saved;
  try {
    saved = JSON.parse(readFileSync(path.join(folder, "egbe-docs", "telemetry", "setup.json"), "utf8"));
  } catch {
    return false;
  }
  if (["declined", "skipped"].includes(saved?.consent)) return true;
  const collector = saved?.collectors?.[HARNESS];
  return Boolean(collector && (collector.enabled === false || collector.stop !== undefined));
}

/** The project folder whose private .env.local holds Egbe's settings: the
 * session's folder or, from a subfolder, the project root above it. */
export function projectFolder(directory, root) {
  for (const folder of [directory, root]) {
    if (!folder) continue;
    try {
      statSync(path.join(folder, ".env.local"));
      return folder;
    } catch {
      // Try the next candidate.
    }
  }
  return directory || root;
}

/** Why logging is off for this folder, or the settings to log with. */
export function loggingSettings(folder, options, environment = process.env) {
  if (options?.sessionLogging === false) return { off: "the plugin's sessionLogging option is false" };
  if (!folder) return { off: "no project folder" };
  let env;
  try {
    env = readEnv(path.join(folder, ".env.local"));
  } catch {
    return { off: "the folder is not set up for Egbe" };
  }
  if (!env) return { off: "the folder's .env.local is readable by others" };
  const choice = env.EGBE_SESSION_LOGGING ?? "";
  if (choice !== "" && choice !== "on") return { off: `EGBE_SESSION_LOGGING=${choice}` };
  if (choice === "" && savedChoiceDeclines(folder)) return { off: "the folder's saved choice declines logging" };
  // The Langfuse OpenCode plugin, set up by hand, already sends sessions to Egbe.
  // `on` overrides a saved decline, never this guard against recording a session twice.
  const langfuse = [environment?.LANGFUSE_BASEURL, environment?.LANGFUSE_BASE_URL, env.LANGFUSE_BASEURL, env.LANGFUSE_BASE_URL];
  if (langfuse.some((url) => String(url ?? "").includes(`/ingest/${HARNESS}`))) {
    return { off: "the Langfuse OpenCode plugin already sends sessions to Egbe" };
  }
  if ((env.OS_URL ?? "").replace(/\/$/, "") !== OS_URL) return { off: "the folder's OS_URL is not Egbe's" };
  const key = env.EGBE_TELEMETRY_SECRET_KEY || env.OS_API_KEY || "";
  if (!/^[A-Za-z0-9_-]{16,}$/.test(key)) return { off: "no usable Egbe key in the folder" };
  const publicKey = env.EGBE_TELEMETRY_PUBLIC_KEY;
  if (publicKey && !/^pk-lf-[A-Za-z0-9-]+$/.test(publicKey)) return { off: "unusable telemetry public key" };
  return { key, osKey: env.OS_API_KEY, publicKey };
}

const text = (value) => {
  const s = typeof value === "string" ? value : JSON.stringify(value ?? null);
  return s.length > MAX_TEXT ? `${s.slice(0, MAX_TEXT)}… [truncated ${s.length - MAX_TEXT} characters]` : s;
};

/** Milliseconds from a number, an ISO string or a Date; undefined otherwise. */
function ms(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" || value instanceof Date) {
    const parsed = new Date(value).getTime();
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

const contentText = (content) =>
  (Array.isArray(content) ? content : [])
    .filter((part) => part?.type === "text" && typeof part.text === "string")
    .map((part) => part.text)
    .join("\n");

const errorText = (error) =>
  error === undefined || error === null ? undefined
    : typeof error === "string" ? error
      : error.data?.message ?? error.message ?? error.name ?? JSON.stringify(error);

/** A run's messages as `{ role, ... }` steps, from OpenCode 1.x `client.session.messages`
 * entries (`{ info, parts }`). */
export function stepsFromV1(entries) {
  const steps = [];
  for (const entry of Array.isArray(entries) ? entries : []) {
    const info = entry?.info ?? {};
    const parts = Array.isArray(entry?.parts) ? entry.parts : [];
    if (info.role === "user") {
      const said = parts.filter((p) => p?.type === "text" && !p.synthetic && !p.ignored).map((p) => p.text).join("\n");
      steps.push({ role: "user", id: info.id, text: said, at: ms(info.time?.created), agent: info.agent,
        model: info.model?.modelID });
    } else if (info.role === "assistant") {
      const tools = parts.filter((p) => p?.type === "tool").map((p) => ({
        id: p.callID, name: p.tool, input: p.state?.input,
        output: p.state?.status === "completed" ? p.state.output : undefined,
        error: p.state?.status === "error" ? p.state.error : undefined,
        start: ms(p.state?.time?.start), end: ms(p.state?.time?.end),
      }));
      steps.push({
        role: "assistant", provider: info.providerID, model: info.modelID, agent: info.mode ?? info.agent,
        text: parts.filter((p) => p?.type === "text" && !p.synthetic).map((p) => p.text).join("\n"),
        tokens: info.tokens, start: ms(info.time?.created), end: ms(info.time?.completed),
        finish: info.finish, error: errorText(info.error), tools,
      });
    }
  }
  return steps;
}

/** A run's messages as steps, from OpenCode 2.x `ctx.session.context` (Session.Message.Info). */
export function stepsFromV2(messages) {
  const steps = [];
  for (const message of Array.isArray(messages) ? messages : []) {
    if (message?.type === "user") {
      steps.push({ role: "user", id: message.id, text: typeof message.text === "string" ? message.text : "",
        at: ms(message.time?.created) });
    } else if (message?.type === "assistant") {
      const content = Array.isArray(message.content) ? message.content : [];
      const tools = content.filter((c) => c?.type === "tool").map((c) => ({
        id: c.id, name: c.name, input: c.state?.input,
        output: c.state?.status === "completed" ? contentText(c.state.content) : undefined,
        error: c.state?.status === "error" ? errorText(c.state.error) ?? contentText(c.state.content) : undefined,
        start: ms(c.time?.ran ?? c.time?.created), end: ms(c.time?.completed),
      }));
      steps.push({
        role: "assistant", provider: message.model?.providerID, model: message.model?.id, agent: message.agent,
        text: content.filter((c) => c?.type === "text").map((c) => c.text).join("\n"),
        tokens: message.tokens, start: ms(message.time?.created), end: ms(message.time?.completed),
        finish: message.finish, error: errorText(message.error), tools,
      });
    } else if (message?.type === "idle") {
      steps.push({ role: "idle", outcome: message.outcome, error: errorText(message.error), at: ms(message.time?.created) });
    }
  }
  return steps;
}

const nanos = (value) => `${BigInt(Math.round(ms(value) ?? Date.now())) * 1_000_000n}`;
const spanId = () => randomBytes(8).toString("hex");
const attributes = (values) =>
  Object.entries(values)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([key, v]) => ({ key, value: typeof v === "number" ? { intValue: String(Math.round(v)) } : { stringValue: String(v) } }));

/** The last run's founder message id, which names the turn so it is sent once. */
export function lastTurnId(steps) {
  for (let i = steps.length - 1; i >= 0; i--) if (steps[i].role === "user") return steps[i].id;
  return undefined;
}

/** The OTLP request body for the session's last turn: the steps from its last founder message on. */
export function turnTraces({ steps, sessionID, workspace, version, api }) {
  let start = -1;
  for (let i = steps.length - 1; i >= 0; i--) {
    if (steps[i].role === "user") {
      start = i;
      break;
    }
  }
  if (start < 0) return undefined;
  const turn = steps.slice(start);
  const prompt = turn[0];
  const traceId = randomBytes(16).toString("hex");
  const root = spanId();
  const replies = turn.filter((s) => s.role === "assistant");
  const reply = replies.map((s) => s.text).filter(Boolean).at(-1) ?? "";
  const idle = turn.find((s) => s.role === "idle");
  const failure = idle?.outcome === "failed" ? idle.error ?? "failed" : replies.find((s) => s.error)?.error;
  const begin = prompt.at ?? replies[0]?.start ?? Date.now();
  const end = Math.max(begin, ...replies.map((s) => s.end ?? s.start ?? begin), idle?.at ?? begin);
  const spans = [];
  let previous = begin;
  for (const step of replies) {
    const started = step.start ?? previous;
    const finished = step.end ?? started;
    const tokens = step.tokens ?? {};
    spans.push({
      traceId, spanId: spanId(), parentSpanId: root, name: step.model || "model", kind: 1,
      startTimeUnixNano: nanos(started), endTimeUnixNano: nanos(finished),
      attributes: attributes({
        "langfuse.observation.type": "generation",
        "gen_ai.operation.name": "chat",
        "gen_ai.system": step.provider,
        "gen_ai.request.model": step.model,
        "gen_ai.usage.input_tokens": tokens.input,
        "gen_ai.usage.output_tokens": tokens.output,
        "gen_ai.usage.cache_read_input_tokens": tokens.cache?.read,
        "langfuse.observation.output": text({
          text: step.text || undefined,
          tool_calls: step.tools.length ? step.tools.map((t) => ({ name: t.name, arguments: t.input })) : undefined,
        }),
        "langfuse.observation.metadata.finish_reason": step.finish,
        "langfuse.observation.level": step.error ? "ERROR" : undefined,
        "langfuse.observation.status_message": step.error ? text(step.error) : undefined,
      }),
      status: { code: step.error ? 2 : 1 },
    });
    for (const tool of step.tools) {
      const failed = tool.error !== undefined;
      spans.push({
        traceId, spanId: spanId(), parentSpanId: root, name: tool.name || "tool", kind: 1,
        startTimeUnixNano: nanos(tool.start ?? started), endTimeUnixNano: nanos(tool.end ?? tool.start ?? finished),
        attributes: attributes({
          "langfuse.observation.type": "tool",
          "gen_ai.operation.name": "execute_tool",
          "gen_ai.tool.name": tool.name,
          "gen_ai.tool.call.id": tool.id,
          "langfuse.observation.input": tool.input === undefined ? undefined : text(tool.input),
          "langfuse.observation.output": text(failed ? tool.error : tool.output ?? ""),
          "langfuse.observation.level": failed ? "ERROR" : undefined,
        }),
        status: { code: failed ? 2 : 1 },
      });
    }
    previous = finished;
  }
  const traceValues = {
    "langfuse.observation.type": "agent",
    "langfuse.trace.name": "OpenCode",
    "langfuse.session.id": sessionID,
    "langfuse.observation.input": text(prompt.text),
    "langfuse.observation.output": text(reply),
    "langfuse.trace.input": text(prompt.text),
    "langfuse.trace.output": text(reply),
    "langfuse.observation.level": failure ? "ERROR" : undefined,
    "langfuse.observation.status_message": failure ? text(failure) : undefined,
    "langfuse.trace.metadata.harness": HARNESS,
    "langfuse.trace.metadata.agent": prompt.agent ?? replies[0]?.agent,
    "langfuse.trace.metadata.model": replies.at(-1)?.model ?? prompt.model,
    "langfuse.trace.metadata.workspace": workspace ? path.basename(workspace) : undefined,
    "langfuse.trace.metadata.plugin_version": version,
    "langfuse.trace.metadata.opencode_api": api,
  };
  spans.unshift({
    traceId, spanId: root, name: "OpenCode turn", kind: 1,
    startTimeUnixNano: nanos(begin), endTimeUnixNano: nanos(end),
    attributes: attributes(traceValues), status: { code: failure ? 2 : 1 },
  });
  return {
    resourceSpans: [{
      resource: { attributes: attributes({ "service.name": "opencode", "egbe.plugin.version": version }) },
      scopeSpans: [{ scope: { name: "egbe-opencode" }, spans }],
    }],
  };
}

/** Sends the turn's traces; returns a short result, never a secret. */
export async function sendTurn({ settings, body, publicKeyCache, fetchImpl = fetch, gateway = GATEWAY }) {
  let publicKey = settings.publicKey || publicKeyCache.get(settings.key);
  if (!publicKey) {
    if (!settings.osKey) return "skipped: no telemetry public key and no Egbe key to find it";
    const res = await fetchImpl(`${OS_URL}/me/limits`, {
      headers: { authorization: `Bearer ${settings.osKey}`, accept: "application/json" },
      redirect: "error", signal: AbortSignal.timeout(15_000),
    });
    const id = res.ok ? (await res.json())?.data?.instance_id : undefined;
    if (!Number.isInteger(id) || id <= 0) return `skipped: the project's key lookup failed (HTTP ${res.status})`;
    publicKey = `pk-lf-egbe-${id}`;
    publicKeyCache.set(settings.key, publicKey);
  }
  const payload = JSON.stringify(body);
  if (Buffer.byteLength(payload) > MAX_BODY) return "skipped: the turn is too large";
  const auth = Buffer.from(`${publicKey}:${settings.key}`).toString("base64");
  for (let attempt = 0; attempt < 3; attempt++) {
    const res = await fetchImpl(`${gateway}/ingest/${HARNESS}/api/public/otel/v1/traces`, {
      method: "POST",
      headers: { authorization: `Basic ${auth}`, "content-type": "application/json" },
      body: payload, redirect: "error", signal: AbortSignal.timeout(30_000),
    });
    if (res.ok) return "sent";
    if (res.status === 401 && !settings.publicKey) publicKeyCache.delete(settings.key);
    if (![429, 503].includes(res.status)) return `failed: HTTP ${res.status}`;
    await new Promise((resolve) => setTimeout(resolve, 2_000 * (attempt + 1)));
  }
  return "failed: the gateway stayed busy";
}
