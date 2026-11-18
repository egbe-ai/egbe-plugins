// Egbe's native OpenClaw plugin, published from egbe-ai/claw-swarm
// plugins/openclaw to the root of egbe-ai/egbe-plugins.
//
// Ships: the Egbe MCP server (declared in openclaw.plugin.json), the bootstrap
// skill, the `egbe_status` and `egbe_connect` tools, `openclaw egbe
// status|update|connect`, connection with a one-time code (connect.js), session
// logging (session-log.js) and a background self-updater.
//
// Self-update: the release JSON { version, commit, ref?, files? } that Egbe's
// release workflow publishes next to the plugin names a git commit of this
// plugin's repository. The updater fetches that commit into a
// private verification repo, checks it (full commit id, package version,
// manifest id, unchanged entry points and capability surface, optional per-file
// SHA-256), then lets OpenClaw apply it:
//   - managed `git:` install: Gateway RPC `plugins.install` {source:"git",
//     spec:"git:<origin>@<commit>", mode:"update"}; OpenClaw re-clones, updates
//     its install record and hot-reloads the plugin;
//   - linked checkout (`plugins install -l`): `git reset --hard <commit>` and
//     `openclaw plugins reload egbe`;
//   - ClawHub install (`openclaw plugins install @egbe/openclaw`): Gateway RPC
//     `plugins.install` {source:"clawhub", packageName, version, mode:"update"},
//     once ClawHub's public API reports that version as published.
// A rejected or ineffective update is rolled back to the previous commit or version.
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { loggingSettings, sendTurn, turnTraces } from "./session-log.js";
import { resolveConnection, saveConnection, savedKey } from "./connect.js";
import { execFile, execFileSync, spawn } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { readFileSync, realpathSync } from "node:fs";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN_ID = "egbe";
const GATEWAY_CONNECT = "egbe.connect";
const CONNECT_FAILED = "EGBE_CONNECT_FAILED";
const CLAWHUB_PACKAGE = "@egbe/openclaw";
// The repository whose release commits ClawHub installs are verified against.
const RELEASE_REPOSITORY = "https://github.com/egbe-ai/egbe-plugins.git";
const CLAWHUB_API = "https://clawhub.ai/api/v1/packages";
const DEFAULT_RELEASE_URL = "https://raw.githubusercontent.com/egbe-ai/egbe-plugins/main/openclaw-release.json";
// OpenClaw imports a captured copy of the plugin (~/.openclaw/tmp/plugin-captures/...),
// so this module's directory tells us which version is *running*; api.rootDir is
// the installed checkout.
const MODULE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const LOADED_VERSION = readJsonSync(path.join(MODULE_ROOT, "package.json")).version;
const RELOAD_GRACE_MS = 3 * 60_000;
const MAX_ROLLBACK_ATTEMPTS = 3;
// Manifest fields that make up the capability surface the user consented to.
const SURFACE_KEYS = ["contracts", "toolMetadata", "mcpServers", "cliCommands", "skills", "providers", "channels", "cliBackends", "hooks"];
let ROOT = MODULE_ROOT;

function readJsonSync(file) {
  return JSON.parse(readFileSync(file, "utf8"));
}
const installedVersion = () => readJsonSync(path.join(ROOT, "package.json")).version;

function settings(pluginConfig) {
  const c = pluginConfig ?? {};
  return {
    autoUpdate: c.autoUpdate !== false,
    releaseUrl: typeof c.releaseUrl === "string" && c.releaseUrl ? c.releaseUrl : DEFAULT_RELEASE_URL,
    intervalMs: Math.max(1, Number(c.checkIntervalMinutes) || 360) * 60_000,
    initialDelayMs: Math.max(0, Number(c.initialDelaySeconds ?? 60)) * 1000,
  };
}

const openclawHome = () => process.env.OPENCLAW_STATE_DIR || path.join(os.homedir(), ".openclaw");
// Kept outside the plugin checkout so reinstalls never touch it.
const stateDir = () => path.join(openclawHome(), "plugin-data", PLUGIN_ID);
const statePath = () => path.join(stateDir(), "updater.json");
const sessionLogPath = () => path.join(stateDir(), "session-log.json");
const gatewayPath = () => path.join(stateDir(), "gateway.json");
const applyLogPath = () => path.join(stateDir(), "apply.log");

async function readJsonState(file) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return {};
  }
}

const readState = () => readJsonState(statePath());

async function writeJsonState(file, value) {
  await fs.mkdir(stateDir(), { recursive: true });
  const tmp = `${file}.${process.pid}.${randomUUID()}.tmp`;
  try {
    await fs.writeFile(tmp, JSON.stringify(value, null, 2), { flag: "wx" });
    await fs.rename(tmp, file);
  } finally {
    await fs.rm(tmp, { force: true });
  }
}

// All updater journal read/merge/write operations run inside withLock.
// Hook and startup status use independent replacement-only files so they cannot
// erase a pending rollback or race its read/modify/write, even across processes.
async function writeState(patch) {
  const next = { ...(await readState()), ...patch, updatedAt: new Date().toISOString() };
  await writeJsonState(statePath(), next);
  return next;
}

// This process's lifetime as the operating system records it: module reloads in
// the same process read the same value, while a restarted container that reuses
// our PID does not, and clock changes don't move it. A lock from this PID and
// lifetime is held (by this or a reloaded instance); one from an earlier lifetime
// of the PID is abandoned. Without an OS record, a same-PID lock counts as held.
function processLifetime() {
  try {
    // Linux: start time in clock ticks since boot (field 22), plus this boot's id.
    const stat = readFileSync("/proc/self/stat", "utf8");
    const fields = stat.slice(stat.lastIndexOf(")") + 2).split(" ");
    return `${readFileSync("/proc/sys/kernel/random/boot_id", "utf8").trim()}:${fields[19]}`;
  } catch {}
  try {
    return execFileSync("ps", ["-o", "lstart=", "-p", String(process.pid)], { encoding: "utf8", timeout: 5_000 }).trim() || undefined;
  } catch {
    return undefined;
  }
}
const PROCESS_LIFETIME = processLifetime();
const sameLifetime = (owner) => PROCESS_LIFETIME === undefined || owner?.lifetime === PROCESS_LIFETIME;

// Cross-process lock shared by the Gateway service and `openclaw egbe update`.
async function withLock(fn) {
  await fs.mkdir(stateDir(), { recursive: true });
  const lock = path.join(stateDir(), "update.lock");
  const busy = () => ({ status: "busy", message: "update lock is held or cannot be safely recovered" });
  let handle;
  try {
    handle = await fs.open(lock, "wx", 0o600);
  } catch (error) {
    if (error.code !== "EEXIST") throw error;
    // Serialize abandoned-owner reclamation so two contenders cannot remove
    // each other's replacement lock. Ambiguous/legacy locks fail closed.
    const reclaim = `${lock}.reclaim`;
    let guard;
    try {
      guard = await fs.open(reclaim, "wx", 0o600);
    } catch (error) {
      if (error.code === "EEXIST") return busy();
      throw error;
    }
    try {
      const owner = await readJsonState(lock);
      if (!Number.isInteger(owner?.pid) || owner.pid <= 0 || typeof owner.token !== "string") return busy();
      if (owner.pid === process.pid) {
        // Without an OS record of lifetimes, only a long-abandoned same-PID lock is recovered.
        const stale = PROCESS_LIFETIME === undefined && Date.now() - (await fs.stat(lock)).mtimeMs > 30 * 60_000;
        if (sameLifetime(owner) && !stale) return busy();
      } else {
        try {
          process.kill(owner.pid, 0);
          return busy();
        } catch (error) {
          if (error.code !== "ESRCH") return busy();
        }
      }
      await fs.rm(lock, { force: true });
      try {
        handle = await fs.open(lock, "wx", 0o600);
      } catch (error) {
        if (error.code === "EEXIST") return busy();
        throw error;
      }
    } finally {
      await guard.close();
      await fs.rm(reclaim, { force: true });
    }
  }
  const token = randomUUID();
  try {
    await handle.writeFile(JSON.stringify({ pid: process.pid, token, lifetime: PROCESS_LIFETIME }));
    return await fn();
  } finally {
    await handle.close();
    const owner = await readJsonState(lock);
    if (owner?.pid === process.pid && owner.token === token) await fs.rm(lock, { force: true });
  }
}

// `where` is ["-C", dir] or ["--git-dir", dir]. Repository hooks never run.
async function git(where, args, encoding = "utf8") {
  const noHooks = path.join(stateDir(), "no-hooks");
  await fs.mkdir(noHooks, { recursive: true });
  return new Promise((resolve, reject) => {
    execFile(
      "git",
      ["-c", `core.hooksPath=${noHooks}`, "-c", "advice.detachedHead=false", ...where, ...args],
      { encoding, maxBuffer: 16 * 1024 * 1024, timeout: 120_000, windowsHide: true, env: { ...process.env, GIT_TERMINAL_PROMPT: "0" } },
      (err, stdout, stderr) => (err ? reject(new Error(`git ${args[0]} failed: ${String(stderr || err.message).trim()}`)) : resolve(stdout)),
    );
  });
}
const gitRoot = (args, enc) => git(["-C", ROOT], args, enc);

function compareVersions(a, b) {
  const pa = String(a).split(".").map(Number);
  const pb = String(b).split(".").map(Number);
  for (let i = 0; i < 3; i++) if ((pa[i] || 0) !== (pb[i] || 0)) return (pa[i] || 0) < (pb[i] || 0) ? -1 : 1;
  return 0;
}

function assertReleaseUrl(raw) {
  const u = new URL(raw);
  if (u.protocol === "https:") return u;
  if (u.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(u.hostname)) return u;
  throw new Error(`release URL must use https (loopback http is allowed for tests): ${raw}`);
}

async function fetchRelease(url) {
  const res = await fetch(assertReleaseUrl(url), {
    redirect: "error",
    signal: AbortSignal.timeout(15_000),
    headers: { accept: "application/json", "user-agent": `egbe-openclaw/${LOADED_VERSION}` },
  });
  if (!res.ok) throw new Error(`release fetch HTTP ${res.status}`);
  const text = await res.text();
  if (text.length > 64 * 1024) throw new Error("release JSON too large");
  const rel = JSON.parse(text);
  if (!/^\d+\.\d+\.\d+$/.test(String(rel.version))) throw new Error("release.version must be x.y.z");
  if (!/^[0-9a-f]{40}([0-9a-f]{24})?$/.test(String(rel.commit))) throw new Error("release.commit must be a full git commit id");
  if (rel.ref !== undefined && !/^[A-Za-z0-9._/-]{1,200}$/.test(String(rel.ref))) throw new Error("release.ref is invalid");
  for (const [p, h] of Object.entries(rel.files ?? {})) {
    if (p.startsWith("/") || p.split("/").includes("..") || !/^[0-9a-f]{64}$/.test(String(h))) {
      throw new Error(`release.files entry is invalid: ${p}`);
    }
  }
  return rel;
}

function surfaceOf(manifest) {
  const norm = (v) =>
    Array.isArray(v)
      ? v.map((x) => (typeof x === "string" ? x : x?.name ?? x?.id ?? JSON.stringify(x))).sort()
      : v && typeof v === "object"
        ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, norm(v[k])]))
        : v;
  const out = {};
  for (const k of SURFACE_KEYS) if (manifest?.[k] !== undefined) out[k] = k === "mcpServers" ? Object.keys(manifest[k]).sort() : norm(manifest[k]);
  return JSON.stringify(out);
}

// Whether ClawHub has finished publishing `version` of the package; anything but
// an explicit "published" (absent, pending, failed, unknown) is not.
async function publishedOnClawHub(version) {
  const res = await fetch(`${CLAWHUB_API}/${encodeURIComponent(CLAWHUB_PACKAGE)}/versions/${version}/publication`, {
    redirect: "error",
    signal: AbortSignal.timeout(15_000),
    headers: { accept: "application/json", "user-agent": `egbe-openclaw/${LOADED_VERSION}` },
  });
  if (!res.ok) return false;
  const body = await res.json().catch(() => ({}));
  return body?.name === CLAWHUB_PACKAGE && body?.version === version && body?.state === "published";
}

// Where the plugin came from and how updates are applied to it.
async function describeInstall() {
  let top = "";
  try {
    top = (await gitRoot(["rev-parse", "--show-toplevel"])).trim();
  } catch {}
  if (!top || realpathSync(top) !== realpathSync(ROOT)) {
    // A ClawHub install is OpenClaw's copy of the package, without git metadata
    // of its own; releases are verified against the published repository.
    if (readJsonSync(path.join(ROOT, "package.json")).name !== CLAWHUB_PACKAGE) {
      throw new Error(`plugin root ${ROOT} is neither a git checkout root nor the ${CLAWHUB_PACKAGE} package`);
    }
    return { kind: "clawhub", origin: RELEASE_REPOSITORY, managed: true, head: installedVersion() };
  }
  const origin = (await gitRoot(["remote", "get-url", "origin"])).trim();
  if (!/^(https:\/\/|ssh:\/\/|git@[\w.-]+:|file:\/\/)/.test(origin)) throw new Error(`unsupported plugin origin ${origin}`);
  // OpenClaw keeps managed git installs at <state dir>/git/git-<hash>/repo, under
  // any profile's state directory.
  let managed = false;
  try {
    managed = /[\\/]git[\\/]git-[0-9a-f]+[\\/]repo$/.test(realpathSync(ROOT));
  } catch {}
  return { kind: managed ? "git" : "linked", origin, managed, head: (await gitRoot(["rev-parse", "HEAD"])).trim() };
}

// Fetch the release commit into a private bare repo and verify it there.
async function fetchAndVerify(rel, origin) {
  const vdir = path.join(stateDir(), "verify.git");
  try {
    await fs.access(path.join(vdir, "HEAD"));
  } catch {
    await git([], ["init", "--bare", "-q", vdir]);
  }
  const v = ["--git-dir", vdir];
  try {
    await git(v, ["fetch", "--no-tags", "--depth=1", origin, rel.commit]);
  } catch (err) {
    if (!rel.ref) throw err;
    await git(v, ["fetch", "--no-tags", "--depth=1", origin, rel.ref]);
  }
  if ((await git(v, ["cat-file", "-t", rel.commit])).trim() !== "commit") throw new Error(`${rel.commit} is not a commit`);
  const show = (p, enc) => git(v, ["show", `${rel.commit}:${p}`], enc);
  const pkg = JSON.parse(await show("package.json"));
  if (pkg.version !== rel.version) throw new Error(`commit has package version ${pkg.version}, release says ${rel.version}`);
  const curPkg = readJsonSync(path.join(ROOT, "package.json"));
  if (JSON.stringify(pkg.openclaw?.extensions) !== JSON.stringify(curPkg.openclaw?.extensions)) {
    throw new Error("release changes openclaw.extensions; a reinstall is required");
  }
  const manifest = JSON.parse(await show("openclaw.plugin.json"));
  if (manifest.id !== PLUGIN_ID) throw new Error(`release manifest id is ${manifest.id}`);
  if (surfaceOf(manifest) !== surfaceOf(readJsonSync(path.join(ROOT, "openclaw.plugin.json")))) {
    const e = new Error("release changes declared capabilities; run `openclaw plugins update egbe` to review and accept them");
    e.code = "NEEDS_CONSENT";
    throw e;
  }
  for (const [p, expected] of Object.entries(rel.files ?? {})) {
    const actual = createHash("sha256").update(await show(p, "buffer")).digest("hex");
    if (actual !== expected) throw new Error(`sha256 mismatch for ${p}`);
  }
}

// The Gateway's argv[1] is the OpenClaw entry (openclaw.mjs). Do not use PATH:
// it can point at a different OpenClaw install than the running Gateway.
function openclawCli() {
  for (const c of [process.env.OPENCLAW_CLI_ENTRY, process.argv[1]].filter(Boolean)) {
    try {
      const real = realpathSync(c);
      if (/[\\/]openclaw[\\/](openclaw\.mjs|dist[\\/](index|entry)\.m?js)$/.test(real)) return real;
    } catch {}
  }
  return undefined;
}

// Run an OpenClaw CLI command against the Gateway. Inside the Gateway it is
// spawned detached and not awaited: applying the update stops this service.
async function runCli(args, { detached, log }) {
  const cli = openclawCli();
  if (!cli) return { ok: false, reason: "cannot locate the openclaw CLI entry" };
  if (detached) {
    const fh = await fs.open(applyLogPath(), "w");
    const child = spawn(process.execPath, [cli, ...args], { detached: true, windowsHide: true, stdio: ["ignore", fh.fd, fh.fd], env: process.env });
    child.unref();
    await fh.close();
    log.info(`[egbe] asked the Gateway to apply the update (pid ${child.pid}, output ${applyLogPath()})`);
    return { ok: true };
  }
  return new Promise((resolve) => {
    execFile(process.execPath, [cli, ...args], { timeout: 11 * 60_000, windowsHide: true, env: process.env }, (err, stdout, stderr) => {
      const out = `${stdout}\n${stderr}`;
      resolve(err || /"ok":\s*false/.test(out) ? { ok: false, reason: out.trim().slice(-400) } : { ok: true });
    });
  });
}

// Move the plugin to `commit` (or, from ClawHub, `version`) and have the running Gateway load it.
async function applyCommit({ commit, origin, managed, kind, version }, opts) {
  if (kind === "clawhub") {
    const params = { source: "clawhub", packageName: CLAWHUB_PACKAGE, version, expectedPluginId: PLUGIN_ID, mode: "update" };
    return runCli(["gateway", "call", "plugins.install", "--json", "--timeout", "600000", "--params", JSON.stringify(params)], opts);
  }
  if (managed) {
    const params = { source: "git", spec: `git:${origin}@${commit}`, mode: "update" };
    return runCli(["gateway", "call", "plugins.install", "--json", "--timeout", "600000", "--params", JSON.stringify(params)], opts);
  }
  if ((await gitRoot(["status", "--porcelain", "--untracked-files=no"])).trim()) {
    throw new Error("plugin checkout has local modifications; refusing to update");
  }
  await gitRoot(["fetch", "--no-tags", "--depth=1", "origin", commit]);
  await gitRoot(["reset", "--hard", commit]);
  return runCli(["plugins", "reload", PLUGIN_ID, "--json"], opts);
}

async function rollback(st, why, log, detached) {
  log.warn(`[egbe] ${why}; restoring ${st.fromVersion} (${st.fromCommit})`);
  const pending = await writeState({
    phase: "rolling-back", rollbackReason: why,
    rollbackRequestedAt: new Date().toISOString(),
    rollbackAttempts: (st.rollbackAttempts ?? 0) + 1,
    lastResult: `rollback pending for ${st.toVersion}: ${why}`, lastError: null,
    badVersions: [...new Set([...(st.badVersions ?? []), st.toVersion])],
  });
  const r = await applyCommit({ commit: st.fromCommit, origin: st.origin, managed: st.managed, kind: st.kind,
                                version: st.fromVersion }, { detached, log });
  if (!r.ok) {
    log.error(`[egbe] rollback could not be applied: ${r.reason}`);
    return writeState({ lastError: `rollback could not be applied: ${r.reason}` });
  }
  // Detached success only acknowledges spawning a CLI. Reconciliation checks
  // both the installed checkout and the code actually running in the Gateway.
  if (!detached && await rollbackIsLive(pending)) return completeRollback(pending);
  return pending;
}

async function installedMismatch(files) {
  if (!files || !Object.keys(files).length) return "the release lists no file hashes";
  for (const [p, expected] of Object.entries(files)) {
    let actual;
    try {
      actual = createHash("sha256").update(await fs.readFile(path.join(ROOT, p))).digest("hex");
    } catch {
      return `${p} is missing`;
    }
    if (actual !== expected) return `sha256 mismatch for ${p}`;
  }
  return undefined;
}

async function rollbackIsLive(st) {
  if (LOADED_VERSION !== st.fromVersion || installedVersion() !== st.fromVersion) return false;
  if (st.kind === "clawhub") return true;
  try {
    return (await gitRoot(["rev-parse", "HEAD"])).trim() === st.fromCommit;
  } catch {
    return false;
  }
}

function completeRollback(st) {
  return writeState({
    phase: "idle", lastError: null,
    lastResult: `rolled back ${st.toVersion}: ${st.rollbackReason}`,
    badVersions: [...new Set([...(st.badVersions ?? []), st.toVersion])],
  });
}

// After an apply request: mark success once the new version runs in the
// Gateway; restore the previous commit if the Gateway rejected it or never loaded it.
async function reconcile(log) {
  const st = await readState();
  if (st.phase === "rolling-back") {
    if (await rollbackIsLive(st)) return completeRollback(st);
    // An operator may recover by installing a fixed release instead. Never
    // downgrade code already installed AND running on a different good version.
    // The predecessor still requires the exact commit check above.
    if (LOADED_VERSION && LOADED_VERSION === installedVersion() &&
        LOADED_VERSION !== st.fromVersion && LOADED_VERSION !== st.toVersion &&
        !(st.badVersions ?? []).includes(LOADED_VERSION)) {
      return writeState({ phase: "idle", lastError: null,
                          lastResult: `recovery resolved by installed ${LOADED_VERSION}` });
    }
    const requestedAt = Date.parse(st.rollbackRequestedAt);
    const out = await fs.readFile(applyLogPath(), "utf8").catch(() => "");
    if ((st.rollbackAttempts ?? 0) < MAX_ROLLBACK_ATTEMPTS &&
        (!Number.isFinite(requestedAt) || Date.now() - requestedAt > RELOAD_GRACE_MS || /"ok":\s*false/.test(out))) {
      return rollback(st, st.rollbackReason || "restoration is still pending", log, true);
    }
    return st;
  }
  if (st.phase !== "applying") return st;
  if (LOADED_VERSION === st.toVersion) {
    // A ClawHub package is verified only once installed: its files must match the
    // release commit's hashes, or the update is rolled back like a rejected one.
    const mismatch = st.kind === "clawhub" ? await installedMismatch(st.files) : undefined;
    if (mismatch) return rollback(st, `the installed ClawHub package differs from the release (${mismatch})`, log, true);
    log.info(`[egbe] update to ${st.toVersion} is live`);
    return writeState({ phase: "idle", lastResult: `updated ${st.fromVersion} -> ${st.toVersion}`, lastSuccessAt: new Date().toISOString() });
  }
  const out = await fs.readFile(applyLogPath(), "utf8").catch(() => "");
  if (/"ok":\s*false/.test(out)) return rollback(st, "the Gateway rejected the update", log, true);
  if (Date.now() - Date.parse(st.requestedAt) > RELOAD_GRACE_MS) return rollback(st, "the update did not take effect", log, true);
  return st;
}

async function checkForUpdate({ cfg, log, force = false, inGateway, followUp }) {
  if (!cfg.autoUpdate && !force) return { status: "disabled" };
  return withLock(async () => {
    const st = inGateway ? await reconcile(log) : await readState();
    if (["applying", "rolling-back"].includes(st.phase)) return { status: "pending", message: st.phase === "rolling-back" ? st.lastResult : `waiting for ${st.toVersion} to load` };
    await writeState({ lastCheckAt: new Date().toISOString() });
    let pending;
    try {
      const rel = await fetchRelease(cfg.releaseUrl);
      const current = installedVersion();
      await writeState({ latestVersion: rel.version });
      if (compareVersions(rel.version, current) <= 0) {
        await writeState({ lastError: null, lastResult: "up to date" });
        return { status: "up-to-date", version: current };
      }
      if (!force && (st.badVersions ?? []).includes(rel.version)) return { status: "skipped", message: `${rel.version} failed before` };
      log.info(`[egbe] update available ${current} -> ${rel.version} (${rel.commit})`);
      const install = await describeInstall();
      if (install.kind === "clawhub" && !(await publishedOnClawHub(rel.version))) {
        // Published to the repository; ClawHub publication follows shortly.
        await writeState({ lastError: null, lastResult: `waiting for ${rel.version} on ClawHub` });
        return { status: "waiting", message: `${rel.version} is not on ClawHub yet` };
      }
      if (install.kind === "clawhub" && !Object.keys(rel.files ?? {}).length) {
        throw new Error("the release lists no file hashes to verify the ClawHub package against");
      }
      await fetchAndVerify(rel, install.origin);
      log.info(`[egbe] verified ${rel.version}; applying via ${install.kind === "linked" ? "checkout + plugins reload" : `plugins.install (${install.kind})`}`);
      pending = await writeState({
        phase: "applying",
        fromVersion: current,
        fromCommit: install.head,
        toVersion: rel.version,
        toCommit: rel.commit,
        origin: install.origin,
        managed: install.managed,
        kind: install.kind,
        files: rel.files ?? null,
        requestedAt: new Date().toISOString(),
        rollbackAttempts: 0, rollbackRequestedAt: null, rollbackReason: null,
        lastError: null,
      });
      const r = await applyCommit({ commit: rel.commit, origin: install.origin, managed: install.managed, kind: install.kind,
                                    version: rel.version }, { detached: inGateway, log });
      if (inGateway) {
        if (!r.ok) throw new Error(r.reason);
        followUp?.();
        return { status: "applying", from: current, to: rel.version };
      }
      if (r.ok) {
        await writeState({ phase: "idle", lastResult: `updated ${current} -> ${rel.version}`, lastSuccessAt: new Date().toISOString() });
        return { status: "updated", from: current, to: rel.version };
      }
      if (/not running|ECONNREFUSED|gateway closed/i.test(r.reason)) {
        if (!install.managed) {
          await writeState({ phase: "idle", lastResult: `installed ${rel.version}; loads on next Gateway start` });
          return { status: "updated", from: current, to: rel.version, reloaded: false };
        }
        pending = undefined; // nothing was applied
        throw new Error("the Gateway is not running; start it and retry");
      }
      throw new Error(r.reason);
    } catch (err) {
      log.warn(`[egbe] update failed, keeping ${installedVersion()}: ${err.message}`);
      if (pending) {
        await rollback(pending, err.message, log, false).catch(async (e) => {
          log.error(`[egbe] rollback failed: ${e.message}`);
          await writeState({ phase: "rolling-back", rollbackReason: err.message, lastError: e.message,
                             lastResult: `rollback pending for ${pending.toVersion}: ${err.message}` });
        });
        if (inGateway) followUp?.(15_000);
      } else {
        await writeState({ phase: "idle", lastError: err.message, lastResult: err.code === "NEEDS_CONSENT" ? "needs consent" : "error" });
      }
      return { status: "error", message: err.message };
    }
  });
}

// Replaces one `mcp.servers` entry in this process through OpenClaw's config
// writer, which works in the Gateway, a local agent run and the CLI. Without it
// (older hosts) the same OpenClaw's CLI sets the entry, which needs either the
// Gateway listening or no process owning the state.
function mcpServerSetter(api, assertCurrent) {
  const mutate = api?.runtime?.config?.mutateConfigFile;
  if (typeof mutate === "function") {
    return async (name, entry) => {
      await mutate({
        afterWrite: { mode: "auto" },
        writeOptions: assertCurrent ? { assertCurrent } : undefined,
        mutate(draft) {
          draft.mcp ??= {};
          draft.mcp.servers ??= {};
          draft.mcp.servers[name] = entry;
        },
      });
    };
  }
  return setMcpServerWithCli;
}

function setMcpServerWithCli(name, entry) {
  const cli = openclawCli();
  if (!cli) return Promise.reject(new Error("cannot locate the openclaw CLI entry"));
  return new Promise((resolve, reject) => {
    execFile(process.execPath, [cli, "config", "set", `mcp.servers.${name}`, JSON.stringify(entry), "--strict-json"],
      { windowsHide: true, env: process.env, timeout: 60_000 },
      (error, stdout, stderr) => (error
        ? reject(new Error(`config set failed: ${`${stdout}${stderr}`.trim().slice(-300)}`))
        : resolve()));
  });
}

// Connects Egbe with a code or key; refuses to replace a different saved key unless asked.
async function connectEgbe(input, { workspaceDir, replace, setMcpServer }) {
  const connection = await resolveConnection(String(input ?? "").trim());
  const current = await savedKey(openclawHome());
  if (current && current !== connection.apiKey && !replace) {
    throw new Error("Egbe is already connected to a business here. Connecting this one replaces it; " +
      "confirm with the founder and retry with replace.");
  }
  await saveConnection({ apiKey: connection.apiKey, stateDir: openclawHome(), workspaceDir, setMcpServer });
  return connection;
}

// Asks the local Gateway's Egbe plugin to connect. Returns undefined when no
// Gateway answers or it runs a plugin without this method; then the CLI connects
// by itself. The Gateway's own failures (an invalid code, say) are thrown.
async function connectThroughGateway(request) {
  let sdk;
  try {
    sdk = await import("openclaw/plugin-sdk/gateway-runtime");
  } catch {
    return undefined;
  }
  try {
    if (!(await sdk.isImplicitLocalGatewayTargetFromCli({}))) return undefined;
    const result = await sdk.callGatewayFromCli(GATEWAY_CONNECT, { timeout: "60000", json: true }, request);
    return { business: result?.business ?? undefined, businessName: result?.businessName ?? undefined };
  } catch (error) {
    if (sdk.isGatewayClientRequestError?.(error) && error?.gatewayCode === CONNECT_FAILED) throw new Error(error.message);
    if (error?.code === CONNECT_FAILED || error?.details?.code === CONNECT_FAILED) throw new Error(error.message);
    return undefined;
  }
}

const defaultWorkspace = () => path.join(openclawHome(), "workspace");

async function statusReport() {
  let commit;
  try {
    commit = (await gitRoot(["rev-parse", "--short", "HEAD"])).trim();
  } catch {}
  return {
    ...(await readState()),
    ...(await readJsonState(sessionLogPath())),
    ...(await readJsonState(gatewayPath())),
    installedVersion: installedVersion(), commit, root: ROOT,
  };
}

export default definePluginEntry({
  id: PLUGIN_ID,
  name: "Egbe",
  description: "Egbe for OpenClaw",
  register(api) {
    const log = api.logger ?? console;
    if (typeof api.rootDir === "string" && api.rootDir) ROOT = api.rootDir;

    api.registerCli(
      async ({ program }) => {
        const cmd = program.command("egbe").description("Egbe plugin status and updates");
        cmd
          .command("status")
          .description("Show the installed Egbe plugin version and update state")
          .option("--json", "print JSON")
          .action(async (opts) => {
            const s = await statusReport();
            if (opts.json) return console.log(JSON.stringify(s, null, 2));
            console.log(`Egbe plugin ${s.installedVersion} (commit ${s.commit ?? "?"}); Gateway running ${s.gatewayVersion ?? "unknown"}`);
            console.log(`Last check: ${s.lastCheckAt ?? "never"}; latest release: ${s.latestVersion ?? "?"}; result: ${s.lastResult ?? "-"}`);
            if (s.lastError) console.log(`Last error: ${s.lastError}`);
            const logged = s.lastSessionLog;
            console.log(`Session logging: ${logged ? `${logged.result} (${logged.at}, ${logged.workspace})` : "no run yet"}`);
          });
        cmd
          .command("connect <code-or-key>")
          .description("Connect Egbe with a one-time code from Egbe's Connect page, or a business key")
          .option("--workspace <dir>", "agent workspace to save the key in", defaultWorkspace())
          .option("--replace", "replace an existing Egbe connection")
          .action(async (input, opts) => {
            // The Gateway resolves paths against its own working directory; send an absolute one.
            const request = { code: String(input ?? "").trim(), workspace: path.resolve(opts.workspace),
                              replace: Boolean(opts.replace) };
            try {
              // A running Gateway connects itself, so its tools work without a restart.
              let c = await connectThroughGateway(request);
              let next = "Ask OpenClaw to set up Egbe.";
              if (!c) {
                c = await connectEgbe(request.code, { workspaceDir: request.workspace, replace: request.replace,
                                                      setMcpServer: mcpServerSetter(api) });
                next = "If OpenClaw's Gateway is running, restart it (openclaw gateway restart), then ask OpenClaw to set up Egbe.";
              }
              console.log(`Connected Egbe${c.businessName ? ` for ${c.businessName}` : ""}${c.business ? ` (${c.business})` : ""}.`);
              console.log(next);
            } catch (error) {
              console.error(error.message);
              process.exitCode = 1;
            }
          });
        cmd
          .command("update")
          .description("Check for an Egbe plugin update now and apply it")
          .action(async () => {
            const r = await checkForUpdate({ cfg: settings(api.pluginConfig), log: console, force: true, inGateway: false });
            console.log(JSON.stringify(r, null, 2));
            if (r.status === "error" || r.status === "busy") process.exitCode = 1;
          });
      },
      { descriptors: [{ name: "egbe", description: "Egbe plugin status and updates", hasSubcommands: true }] },
    );

    api.registerTool({
      name: "egbe_status",
      description: "Report the Egbe plugin version running in this Gateway and its auto-update state.",
      parameters: { type: "object", properties: {}, additionalProperties: false },
      async execute() {
        const s = { loadedVersion: LOADED_VERSION, ...(await statusReport()) };
        return { content: [{ type: "text", text: JSON.stringify(s) }], details: s };
      },
    });

    api.registerTool((ctx) => ({
      name: "egbe_connect",
      description: "Connect this OpenClaw to the founder's Egbe business with the one-time connection code the founder " +
        "sent (EGBE-XXXX-XXXX, from the business's Connect page in Egbe), or an Egbe business key. Use only a code or key " +
        "the founder sent you directly. Egbe's tools are available from the next message.",
      parameters: {
        type: "object",
        properties: {
          code: { type: "string", description: "The connection code or business key the founder sent." },
          replace: { type: "boolean", description: "Replace an existing Egbe connection; only after the founder confirms." },
        },
        required: ["code"],
        additionalProperties: false,
      },
      async execute(_id, params) {
        // The host's live check that this invocation may still act; the config
        // writer rechecks it right before publishing the change.
        const ownerCheck = typeof ctx?.assertInvocationCurrent === "function" ? ctx.assertInvocationCurrent : undefined;
        if (ctx?.senderIsOwner === false) {
          return { content: [{ type: "text", text: "Only this OpenClaw's owner can connect Egbe." }], details: { connected: false } };
        }
        try {
          const c = await connectEgbe(params?.code, {
            workspaceDir: ctx?.workspaceDir, replace: params?.replace === true,
            setMcpServer: mcpServerSetter(api, ownerCheck),
          });
          const details = { connected: true, business: c.business ?? null, business_name: c.businessName ?? null };
          return {
            content: [{ type: "text", text: `Egbe is connected${c.businessName ? ` for ${c.businessName}` : ""}. ` +
              "Its tools are available from the founder's next message; then call egbe_setup and continue setup. " +
              "The workspace already has this business's saved credentials." }],
            details,
          };
        } catch (error) {
          return { content: [{ type: "text", text: error.message }], details: { connected: false } };
        }
      },
    }), { name: "egbe_connect" });

    // `openclaw egbe connect` hands the code to a running Gateway, which saves the
    // connection itself and loads Egbe's MCP server without a restart.
    api.registerGatewayMethod?.(GATEWAY_CONNECT, async ({ params, respond }) => {
      try {
        const c = await connectEgbe(params?.code, {
          workspaceDir: typeof params?.workspace === "string" ? params.workspace : defaultWorkspace(),
          replace: params?.replace === true, setMcpServer: mcpServerSetter(api),
        });
        respond(true, { business: c.business ?? null, businessName: c.businessName ?? null });
      } catch (error) {
        respond(false, undefined, { code: CONNECT_FAILED, message: error.message });
      }
    }, { scope: "operator.admin" });

    // Session logging runs wherever agent runs do, including embedded `openclaw agent --local`.
    const publicKeys = new Map();
    api.on("agent_end", async (event, ctx) => {
      const workspace = ctx?.workspaceDir;
      let result;
      try {
        const logging = loggingSettings(workspace, api.pluginConfig, api.config);
        if (logging.off) {
          result = `off: ${logging.off}`;
        } else {
          const body = turnTraces({ messages: event?.messages, ctx, success: event?.success, error: event?.error, version: LOADED_VERSION });
          result = body ? await sendTurn({ settings: logging, body, publicKeyCache: publicKeys }) : "skipped: no founder message in the run";
        }
      } catch (err) {
        result = `failed: ${err.message}`;
      }
      if (!result.startsWith("sent")) log.debug?.(`[egbe] session logging ${result}`);
      await writeJsonState(sessionLogPath(), { lastSessionLog: { at: new Date().toISOString(), result, workspace: workspace ? path.basename(workspace) : "" } })
        .catch(() => {});
    });
    if (api.registrationMode !== "full") return;

    const cfg = settings(api.pluginConfig);
    api.registerService({
      id: "egbe-updater",
      apiVersion: 2,
      async start({ scheduler }) {
        log.info(`[egbe] plugin ${LOADED_VERSION} started (autoUpdate=${cfg.autoUpdate})`);
        await writeJsonState(gatewayPath(), { gatewayVersion: LOADED_VERSION, gatewayStartedAt: new Date().toISOString() });
        const followUp = (delayMs = RELOAD_GRACE_MS + 5_000) =>
          scheduler.schedule({ id: "reconcile", delayMs, run: async () => {
            const state = await withLock(() => reconcile(log));
            if (state.phase === "applying" || state.status === "busy" ||
                state.phase === "rolling-back" && (state.rollbackAttempts ?? 0) < MAX_ROLLBACK_ATTEMPTS) followUp(15_000);
            return state;
          } });
        const st = await withLock(() => reconcile(log)).catch((e) => (log.warn(`[egbe] reconcile failed: ${e.message}`), {}));
        if (st.phase === "applying" || st.status === "busy" ||
            st.phase === "rolling-back" && (st.rollbackAttempts ?? 0) < MAX_ROLLBACK_ATTEMPTS) followUp(15_000);
        if (!cfg.autoUpdate) return;
        scheduler.schedule({
          id: "update-check",
          delayMs: cfg.initialDelayMs,
          everyMs: cfg.intervalMs,
          run: () => checkForUpdate({ cfg, log, inGateway: true, followUp }),
        });
      },
    });
  },
});
