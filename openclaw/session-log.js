// Egbe session logging for OpenClaw.
//
// On by default in an agent workspace set up for Egbe, as the Egbe plugin's
// README and Egbe's setup disclose; OpenClaw itself also requires the operator
// to grant the plugin conversation access
// (plugins.entries.egbe.hooks.allowConversationAccess). After each agent run
// (`agent_end`), it sends that run's turn (the founder's message, model calls
// with usage, tool calls with their results, and the reply) as OTLP traces to
// Egbe's telemetry gateway, authenticated with the workspace's own Egbe key, and
// grouped into the OpenClaw session. It stays off when the workspace has no
// private .env.local with Egbe credentials, when that file says
// EGBE_SESSION_LOGGING=off, when the workspace's saved choice declines logging or
// stops the openclaw collector, when the plugin's sessionLogging setting is
// false, or when OpenClaw's own OpenTelemetry export already sends to Egbe. It
// never fails a run: errors are logged and the turn is skipped.
import { randomBytes } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import path from "node:path";

const OS_URL = "https://os.hz.egbe.dev";
const GATEWAY = "https://observe.hz.egbe.dev/telemetry";
const HARNESS = "openclaw";
const MAX_TEXT = 16_000;
const MAX_BODY = 7 * 1024 * 1024;

function readEnv(file) {
  // Only the workspace's private settings count: setup writes .env.local with
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
function savedChoiceDeclines(workspace) {
  let saved;
  try {
    saved = JSON.parse(readFileSync(path.join(workspace, "egbe-docs", "telemetry", "setup.json"), "utf8"));
  } catch {
    return false;
  }
  if (["declined", "skipped"].includes(saved?.consent)) return true;
  const collector = saved?.collectors?.[HARNESS];
  return Boolean(collector && (collector.enabled === false || collector.stop !== undefined));
}

/** Why logging is off for this workspace, or the settings to log with. */
export function loggingSettings(workspace, pluginConfig, openclawConfig) {
  if (pluginConfig?.sessionLogging === false) return { off: "the plugin's sessionLogging setting is false" };
  if (!workspace) return { off: "no workspace" };
  let env;
  try {
    env = readEnv(path.join(workspace, ".env.local"));
  } catch {
    return { off: "the workspace is not set up for Egbe" };
  }
  if (!env) return { off: "the workspace's .env.local is readable by others" };
  const choice = env.EGBE_SESSION_LOGGING ?? "";
  if (choice !== "" && choice !== "on") return { off: `EGBE_SESSION_LOGGING=${choice}` };
  if (choice === "" && savedChoiceDeclines(workspace)) return { off: "the workspace's saved choice declines logging" };
  const otel = openclawConfig?.diagnostics?.otel;
  if (choice === "" && otel?.enabled && String(otel.tracesEndpoint ?? otel.endpoint ?? "").includes(`/ingest/${HARNESS}`)) {
    return { off: "OpenClaw's OpenTelemetry export already sends sessions to Egbe" };
  }
  if ((env.OS_URL ?? "").replace(/\/$/, "") !== OS_URL) return { off: "the workspace's OS_URL is not Egbe's" };
  const key = env.EGBE_TELEMETRY_SECRET_KEY || env.OS_API_KEY || "";
  if (!/^[A-Za-z0-9_-]{16,}$/.test(key)) return { off: "no usable Egbe key in the workspace" };
  const publicKey = env.EGBE_TELEMETRY_PUBLIC_KEY;
  if (publicKey && !/^pk-lf-[A-Za-z0-9-]+$/.test(publicKey)) return { off: "unusable telemetry public key" };
  return { key, osKey: env.OS_API_KEY, publicKey };
}

const text = (value) => {
  const s = typeof value === "string" ? value : JSON.stringify(value ?? null);
  return s.length > MAX_TEXT ? `${s.slice(0, MAX_TEXT)}… [truncated ${s.length - MAX_TEXT} characters]` : s;
};

function contentText(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content.filter((part) => part?.type === "text" && typeof part.text === "string").map((part) => part.text).join("\n");
}

const nanos = (ms) => `${BigInt(Math.round(Number(ms) || Date.now())) * 1_000_000n}`;
const spanId = () => randomBytes(8).toString("hex");
const attributes = (values) =>
  Object.entries(values)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([key, v]) => ({ key, value: typeof v === "number" ? { intValue: String(Math.round(v)) } : { stringValue: String(v) } }));

/** The OTLP request body for the run's turn: the messages from its last founder message on. */
export function turnTraces({ messages, ctx, success, error, version }) {
  const list = Array.isArray(messages) ? messages : [];
  let start = -1;
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i]?.role === "user") {
      start = i;
      break;
    }
  }
  if (start < 0) return undefined;
  const turn = list.slice(start);
  const prompt = turn[0];
  const traceId = randomBytes(16).toString("hex");
  const root = spanId();
  const session = [ctx?.agentId || "main", ctx?.sessionId || ctx?.sessionKey || "unknown"].join(":");
  const replies = turn.filter((m) => m?.role === "assistant");
  const reply = contentText(replies.at(-1)?.content);
  const begin = prompt.timestamp ?? Date.now();
  const end = turn.at(-1)?.timestamp ?? Date.now();
  const spans = [];
  const calls = new Map();
  let previous = begin;
  for (const message of turn.slice(1)) {
    if (message?.role === "assistant") {
      const parts = Array.isArray(message.content) ? message.content : [];
      const toolCalls = parts.filter((part) => part?.type === "toolCall");
      for (const call of toolCalls) calls.set(call.id, { call, at: message.timestamp });
      const usage = message.usage ?? {};
      spans.push({
        traceId, spanId: spanId(), parentSpanId: root, name: message.model || "model", kind: 1,
        startTimeUnixNano: nanos(previous), endTimeUnixNano: nanos(message.timestamp),
        attributes: attributes({
          "langfuse.observation.type": "generation",
          "gen_ai.operation.name": "chat",
          "gen_ai.system": message.provider,
          "gen_ai.request.model": message.model,
          "gen_ai.usage.input_tokens": usage.input,
          "gen_ai.usage.output_tokens": usage.output,
          "gen_ai.usage.cache_read_input_tokens": usage.cacheRead,
          "langfuse.observation.output": text({
            text: contentText(message.content) || undefined,
            tool_calls: toolCalls.length ? toolCalls.map((call) => ({ name: call.name, arguments: call.arguments })) : undefined,
          }),
          "langfuse.observation.metadata.stop_reason": message.stopReason,
        }),
        status: { code: message.stopReason === "error" ? 2 : 1 },
      });
    } else if (message?.role === "toolResult") {
      const started = calls.get(message.toolCallId);
      spans.push({
        traceId, spanId: spanId(), parentSpanId: root, name: message.toolName || "tool", kind: 1,
        startTimeUnixNano: nanos(started?.at ?? previous), endTimeUnixNano: nanos(message.timestamp),
        attributes: attributes({
          "langfuse.observation.type": "tool",
          "gen_ai.operation.name": "execute_tool",
          "gen_ai.tool.name": message.toolName,
          "langfuse.observation.input": started ? text(started.call.arguments) : undefined,
          "langfuse.observation.output": text(contentText(message.content)),
          "langfuse.observation.level": message.isError ? "ERROR" : undefined,
        }),
        status: { code: message.isError ? 2 : 1 },
      });
    }
    if (message?.timestamp) previous = message.timestamp;
  }
  const traceValues = {
    "langfuse.observation.type": "agent",
    "langfuse.trace.name": "OpenClaw",
    "langfuse.session.id": session,
    "langfuse.observation.input": text(contentText(prompt.content)),
    "langfuse.observation.output": text(reply),
    "langfuse.trace.input": text(contentText(prompt.content)),
    "langfuse.trace.output": text(reply),
    "langfuse.observation.level": success === false ? "ERROR" : undefined,
    "langfuse.observation.status_message": error ? text(error) : undefined,
    "langfuse.trace.metadata.harness": HARNESS,
    "langfuse.trace.metadata.agent_id": ctx?.agentId,
    "langfuse.trace.metadata.trigger": ctx?.trigger,
    "langfuse.trace.metadata.channel": ctx?.channel ?? ctx?.messageProvider,
    "langfuse.trace.metadata.model": ctx?.modelId,
    "langfuse.trace.metadata.workspace": ctx?.workspaceDir ? path.basename(ctx.workspaceDir) : undefined,
    "langfuse.trace.metadata.plugin_version": version,
  };
  spans.unshift({
    traceId, spanId: root, name: "OpenClaw turn", kind: 1,
    startTimeUnixNano: nanos(begin), endTimeUnixNano: nanos(end),
    attributes: attributes(traceValues), status: { code: success === false ? 2 : 1 },
  });
  return {
    resourceSpans: [{
      resource: { attributes: attributes({ "service.name": "openclaw", "egbe.plugin.version": version }) },
      scopeSpans: [{ scope: { name: "egbe-openclaw" }, spans }],
    }],
  };
}

/** Sends the turn's traces; returns a short result for the plugin's state. */
export async function sendTurn({ settings, body, publicKeyCache, fetchImpl = fetch }) {
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
  let payload = JSON.stringify(body);
  if (Buffer.byteLength(payload) > MAX_BODY) return "skipped: the turn is too large";
  const auth = Buffer.from(`${publicKey}:${settings.key}`).toString("base64");
  for (let attempt = 0; attempt < 3; attempt++) {
    const res = await fetchImpl(`${GATEWAY}/ingest/${HARNESS}/api/public/otel/v1/traces`, {
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
