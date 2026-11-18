// Connect OpenClaw to one Egbe business without a browser.
//
// The founder gets a one-time connection code on the business's Connect page in
// Egbe (Connect → OpenClaw), valid once for 10 minutes, and sends it to this
// OpenClaw in a chat or runs `openclaw egbe connect <code>`. The code is
// exchanged at Egbe for the business's project key (the same key Egbe's copied
// instructions carry). A business key itself is accepted too. The key is saved
// in OpenClaw's trusted `.env`, Egbe's MCP server is configured in
// `mcp.servers.egbe` to send it, which replaces the plugin's OAuth sign-in for
// that server, and the agent workspace gets the key in its private `.env.local`.
import fs from "node:fs/promises";
import path from "node:path";

export const DASHBOARD_URL = "https://dashboard.egbe.ai";
export const OS_URL = "https://os.hz.egbe.dev";
export const KEY_VARIABLE = "EGBE_API_KEY";

/** A connection code, without spaces, dashes or its EGBE prefix; or undefined. */
export function codeOf(input) {
  const compact = String(input ?? "").toUpperCase().replace(/[\s-]/g, "").replace(/^EGBE/, "");
  return /^[0-9A-Z]{8}$/.test(compact) ? compact : undefined;
}

const isKey = (input) => /^[A-Za-z0-9_-]{24,256}$/.test(String(input ?? ""));

async function json(res) {
  try {
    return await res.json();
  } catch {
    return {};
  }
}

/** Exchanges a code at Egbe, or checks a key with Egbe; returns what to save. */
export async function resolveConnection(input, { fetchImpl = fetch } = {}) {
  const code = codeOf(input);
  if (code) {
    const res = await fetchImpl(`${DASHBOARD_URL}/api/agent/setup-codes/redeem`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify({ code }),
      redirect: "error",
      signal: AbortSignal.timeout(15_000),
    });
    const body = await json(res);
    if (res.status === 429) throw new Error("Too many attempts; wait a minute and try again.");
    // Egbe keeps the code unused when it could not complete the exchange.
    if (res.status >= 500) throw new Error("Egbe could not complete the connection right now; try the same code again shortly.");
    if (!res.ok) {
      throw new Error("This connection code is not valid: it may have expired, been used already or been mistyped. " +
        "Get a new one on the business's Connect page in Egbe.");
    }
    if (body.os_url !== OS_URL || !isKey(body.api_key)) throw new Error("Egbe returned an unexpected connection.");
    return { apiKey: body.api_key, business: body.business, businessName: body.business_name };
  }
  if (!isKey(input)) {
    throw new Error("Expected a connection code like EGBE-XXXX-XXXX from Egbe, or an Egbe business key.");
  }
  const res = await fetchImpl(`${OS_URL}/me/limits`, {
    headers: { authorization: `Bearer ${input}`, accept: "application/json" },
    redirect: "error",
    signal: AbortSignal.timeout(15_000),
  });
  const instance = (await json(res))?.data?.instance_id;
  if (!res.ok || !Number.isInteger(instance)) throw new Error("Egbe did not accept this key.");
  return { apiKey: input, business: undefined, businessName: undefined };
}

/** Sets `values` in a dotenv file, keeping its other lines; the file stays private. */
export async function upsertEnv(file, values) {
  let lines = [];
  try {
    lines = (await fs.readFile(file, "utf8")).split(/\r?\n/);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  const pending = new Map(Object.entries(values));
  lines = lines.map((line) => {
    const match = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=/.exec(line);
    if (!match || !pending.has(match[1])) return line;
    const value = pending.get(match[1]);
    pending.delete(match[1]);
    return `${match[1]}=${value}`;
  });
  while (lines.length && lines.at(-1) === "") lines.pop();
  for (const [name, value] of pending) lines.push(`${name}=${value}`);
  await fs.mkdir(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  await fs.writeFile(tmp, `${lines.join("\n")}\n`, { mode: 0o600 });
  await fs.chmod(tmp, 0o600);
  await fs.rename(tmp, file);
}

/** The `mcp.servers.egbe` entry that sends the saved key. */
export function mcpServer() {
  return {
    url: `${OS_URL}/mcp`,
    transport: "streamable-http",
    headers: { Authorization: `Bearer \${${KEY_VARIABLE}}` },
  };
}

/** The key Egbe's MCP server is configured with, if any. */
export async function savedKey(stateDir) {
  try {
    const text = await fs.readFile(path.join(stateDir, ".env"), "utf8");
    return new RegExp(`^\\s*(?:export\\s+)?${KEY_VARIABLE}=(.*)$`, "m").exec(text)?.[1]?.trim() || undefined;
  } catch {
    return undefined;
  }
}

/**
 * Saves the connection. `setMcpServer(name, entry)` replaces that OpenClaw MCP
 * server entry as a whole, so an earlier OAuth entry keeps no `auth` setting.
 * `workspaceDir`, when known, gets OS_URL and OS_API_KEY in its `.env.local`.
 */
export async function saveConnection({ apiKey, stateDir, workspaceDir, setMcpServer }) {
  await upsertEnv(path.join(stateDir, ".env"), { [KEY_VARIABLE]: apiKey });
  // A running Gateway read its .env at start; set the key for this process too, so
  // the config change below takes effect without a restart.
  process.env[KEY_VARIABLE] = apiKey;
  await setMcpServer("egbe", mcpServer());
  if (workspaceDir) {
    await upsertEnv(path.join(workspaceDir, ".env.local"), { OS_URL, OS_API_KEY: apiKey });
    const ignore = path.join(workspaceDir, ".gitignore");
    const ignored = await fs.readFile(ignore, "utf8").catch(() => undefined);
    if (ignored !== undefined && !/^\.env\.local$/m.test(ignored)) {
      await fs.appendFile(ignore, `${ignored.endsWith("\n") ? "" : "\n"}.env.local\n`);
    }
  }
}
