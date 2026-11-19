#!/usr/bin/env node
/** Create or reuse one private validation identity in canonical Product Auth. */
import { spawnSync } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { chmod, mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";

export const DEFAULT_COOKIE_NAME = "egbe_session";
const DEFAULT_TTL_HOURS = 24;
const MIN_REUSE_MS = 5 * 60 * 1000;

export function hashSessionToken(token) {
  return createHash("sha256").update(String(token), "utf8").digest("hex");
}

function normalizedOrigin(value) {
  const parsed = new URL(String(value || ""));
  if (!new Set(["http:", "https:"]).has(parsed.protocol)) {
    throw new Error("--origin must be an HTTP(S) product origin");
  }
  return parsed.origin;
}

function positiveHours(value) {
  const hours = Number(value || DEFAULT_TTL_HOURS);
  if (!Number.isFinite(hours) || hours <= 0 || hours > 168) {
    throw new Error("--ttl-hours must be between 0 and 168");
  }
  return hours;
}

export function parseArgs(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith("--") || index + 1 >= argv.length) {
      throw new Error(`invalid argument: ${key}`);
    }
    values[key.slice(2)] = argv[index + 1];
    index += 1;
  }
  if (!values.origin) throw new Error("--origin is required");
  if (!values.state) throw new Error("--state is required");
  const cookieName = String(values["cookie-name"] || DEFAULT_COOKIE_NAME).trim();
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(cookieName)) {
    throw new Error("--cookie-name is invalid");
  }
  return {
    origin: normalizedOrigin(values.origin),
    statePath: resolve(values.state),
    browserSession: String(values["browser-session"] || "").trim(),
    cookieName,
    ttlHours: positiveHours(values["ttl-hours"]),
  };
}

async function readPrivateState(path) {
  try {
    const value = JSON.parse(await readFile(path, "utf8"));
    return value && typeof value === "object" ? value : null;
  } catch {
    return null;
  }
}

export async function writePrivateState(path, value) {
  const parent = dirname(path);
  await mkdir(parent, { recursive: true, mode: 0o700 });
  await chmod(parent, 0o700);
  const temporary = `${path}.${process.pid}.${randomBytes(4).toString("hex")}.tmp`;
  await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
  await chmod(temporary, 0o600);
  await rename(temporary, path);
  await chmod(path, 0o600);
}

function newValidationEmail() {
  return `egbe-validation+${randomBytes(10).toString("hex")}@example.invalid`;
}

function stateMatches(value, { origin, cookieName, now }) {
  return Boolean(
    value
      && value.version === 1
      && value.origin === origin
      && value.cookie_name === cookieName
      && typeof value.email === "string"
      && typeof value.session_token === "string"
      && value.session_token.length >= 32
      && Date.parse(value.expires_at || "") > now.getTime() + MIN_REUSE_MS,
  );
}

export async function ensureValidationSession(
  client,
  { origin, cookieName = DEFAULT_COOKIE_NAME, ttlHours = DEFAULT_TTL_HOURS, state = null, now = new Date() },
) {
  if (stateMatches(state, { origin, cookieName, now })) {
    const existing = await client.query(
      `select 1
         from users u
         join sessions s on s.user_id = u.id
        where lower(u.email) = lower($1)
          and s.token_hash = $2
          and s.revoked_at is null
          and s.expires_at > $3`,
      [state.email, hashSessionToken(state.session_token), now.toISOString()],
    );
    if (existing.rowCount > 0) return { state, reused: true };
  }

  const email = state?.origin === origin && state?.email
    ? String(state.email)
    : newValidationEmail();
  const sessionToken = randomBytes(32).toString("base64url");
  const tokenHash = hashSessionToken(sessionToken);
  const expiresAt = new Date(now.getTime() + ttlHours * 60 * 60 * 1000);

  await client.query("begin");
  try {
    const user = await client.query(
      `insert into users (email, password_hash)
       values ($1, null)
       on conflict ((lower(email))) do update set updated_at = now()
       returning id`,
      [email],
    );
    const userId = user.rows[0]?.id;
    if (!userId) throw new Error("validation user could not be resolved");
    await client.query(
      `update sessions
          set revoked_at = coalesce(revoked_at, now())
        where user_id = $1 and revoked_at is null`,
      [userId],
    );
    await client.query(
      `insert into sessions (user_id, token_hash, expires_at)
       values ($1, $2, $3)`,
      [userId, tokenHash, expiresAt.toISOString()],
    );
    await client.query("commit");
  } catch (error) {
    await client.query("rollback").catch(() => {});
    throw error;
  }

  return {
    reused: false,
    state: {
      version: 1,
      origin,
      email,
      cookie_name: cookieName,
      session_token: sessionToken,
      expires_at: expiresAt.toISOString(),
    },
  };
}

export function loadBrowserSession(state, browserSession, runner = spawnSync) {
  if (!browserSession) return;
  const binary = process.env.EGBE_AGENT_BROWSER_BIN || "agent-browser";
  const common = ["--session", browserSession];
  for (const args of [
    [...common, "open", state.origin],
    [...common, "cookies", "set", state.cookie_name, state.session_token],
  ]) {
    const result = runner(binary, args, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    if (result.error || result.status !== 0) {
      throw new Error("agent-browser could not load the validation session");
    }
  }
}

export function publicResult({ reused, statePath, browserSession }) {
  return {
    ok: true,
    reused,
    state_path: statePath,
    browser_session: browserSession || null,
  };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const databaseUrl = String(process.env.DATABASE_URL || "");
  if (!databaseUrl) throw new Error("DATABASE_URL is not set");
  const imported = await import("pg");
  const Client = imported.default?.Client || imported.Client;
  if (!Client) throw new Error("pg Client is unavailable");

  const client = new Client({ connectionString: databaseUrl });
  await client.connect();
  try {
    const previous = await readPrivateState(options.statePath);
    const result = await ensureValidationSession(client, {
      origin: options.origin,
      cookieName: options.cookieName,
      ttlHours: options.ttlHours,
      state: previous,
    });
    await writePrivateState(options.statePath, result.state);
    loadBrowserSession(result.state, options.browserSession);
    process.stdout.write(`${JSON.stringify(publicResult({
      reused: result.reused,
      statePath: options.statePath,
      browserSession: options.browserSession,
    }))}\n`);
  } finally {
    await client.end();
  }
}

if (import.meta.url === pathToFileURL(process.argv[1] || "").href) {
  main().catch((error) => {
    process.stderr.write(`create-validation-session failed: ${String(error?.message || error)}\n`);
    process.exitCode = 1;
  });
}
