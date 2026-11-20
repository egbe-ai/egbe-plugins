// Egbe's OpenCode plugin updates itself from npm.
//
// OpenCode 1.x installs an unpinned npm plugin once into its cache
// (`<cache>/opencode/packages/@egbe-ai/opencode@latest/`) and loads that copy on
// every later start without checking npm again. OpenCode 2.x checks unpinned
// npm plugins for new versions once a day but only marks them outdated: the
// update runs when someone runs `opencode plugin update`. So, in a long-running
// OpenCode, the plugin checks npm itself, a minute after it loads and every six
// hours, never at import and never in the way of a turn:
//
//   1. It reads `@egbe-ai/opencode` from the npm registry. A newer `latest` version
//      whose declared capabilities (package.json `egbe.capabilities`: MCP servers,
//      tools, commands and hooks) differ from the running version's is not
//      installed automatically; the state file says to update by hand.
//   2. It downloads that version's tarball from the registry's own host, checks
//      it against the registry's `dist.integrity` (SHA-512), unpacks it into a
//      staging folder and checks its name, version and capabilities, then loads
//      the staged copy with updates and logging off and checks that it registers
//      the Egbe connector. Nothing it downloaded runs before the integrity check.
//   3. OpenCode 1.x: it swaps the staged copy into OpenCode's cache and keeps the
//      previous copy until the new version has loaded; a failed swap restores the
//      previous copy. The next OpenCode start loads the new version.
//      OpenCode 2.x: it asks OpenCode to update the plugin
//      (`opencode plugin update <target>`), which installs the same version
//      through OpenCode's own npm installer and its integrity checks and reloads it.
//
// A pinned install (an exact version or a range) and an install from a folder,
// such as a clone of egbe-ai/egbe-plugins (updated with `git pull`), are left
// alone. The `autoUpdate: false` option turns this off. Every check is recorded
// under `update` in the plugin's state file.
import { createHash, randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { gunzipSync } from "node:zlib";
import { readState, stateDir, writeState } from "./state.js";

export const PACKAGE = "@egbe-ai/opencode";
const SCOPE = PACKAGE.split("/")[0];
export const REGISTRY = "https://registry.npmjs.org";
const MAX_PACKUMENT = 16 * 1024 * 1024;
const MAX_TARBALL = 32 * 1024 * 1024;
const LOCK_STALE = 15 * 60 * 1000;

/** The updater's settings from the plugin options. */
export function updaterSettings(options) {
  const o = options ?? {};
  const number = (value, fallback, min) => (typeof value === "number" && Number.isFinite(value) && value >= min ? value : fallback);
  let registry = REGISTRY;
  if (o.registryUrl !== undefined) {
    // A loopback registry for tests; otherwise only npm's. A bad value turns updates off.
    let url;
    try {
      url = new URL(String(o.registryUrl));
    } catch {
      url = undefined;
    }
    const loopback = url?.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
    if (!url || (url.href.replace(/\/$/, "") !== REGISTRY && !loopback)) {
      return { enabled: false, registry, intervalMs: 0, initialDelayMs: 0, error: "registryUrl must be npm's registry or a loopback test registry" };
    }
    registry = url.href.replace(/\/$/, "");
  }
  return {
    enabled: o.autoUpdate !== false,
    registry,
    intervalMs: number(o.checkIntervalMinutes, 360, 1) * 60 * 1000,
    initialDelayMs: number(o.initialDelaySeconds, 60, 0) * 1000,
  };
}

export function compareVersions(a, b) {
  const parse = (v) => String(v).split("-")[0].split(".").map((n) => Number.parseInt(n, 10) || 0);
  const [x, y] = [parse(a), parse(b)];
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1;
  return 0;
}

const sameCapabilities = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

/** How this copy was installed: OpenCode 1.x's npm cache, a folder, or a pinned spec.
 * OpenCode 1.x keeps a package at `<cache>/packages/<spec>/node_modules/<name>`. */
export function v1Install(moduleRoot) {
  const scope = path.dirname(moduleRoot);
  const modules = path.dirname(scope);
  const specDir = path.dirname(modules);
  const scopeDir = path.dirname(specDir);
  const packages = path.dirname(scopeDir);
  const isCache = path.basename(moduleRoot) === "opencode" && path.basename(scope) === SCOPE
    && path.basename(modules) === "node_modules" && path.basename(scopeDir) === SCOPE && path.basename(packages) === "packages";
  if (!isCache) return { kind: "folder" };
  const spec = path.basename(specDir);
  if (spec !== "opencode@latest") return { kind: "pinned", spec: `${SCOPE}/${spec}` };
  return { kind: "npm", spec: `${PACKAGE}@latest`, packageDir: moduleRoot };
}

/** The plugin's entry in OpenCode 2.x's plugin inventory, as an install kind. */
export function v2Install(inventory) {
  const list = Array.isArray(inventory?.data) ? inventory.data : Array.isArray(inventory) ? inventory : [];
  const entry = list.find((p) => p?.id === "egbe") ?? list.find((p) => p?.source?.target?.startsWith?.(PACKAGE));
  const source = entry?.source;
  if (!source) return { kind: "unknown" };
  if (source.type !== "package") return { kind: "folder" };
  const target = String(source.target);
  if (target !== PACKAGE && target !== `${PACKAGE}@latest`) return { kind: "pinned", spec: target };
  return { kind: "npm", target };
}

function lock(dir) {
  const file = path.join(dir, "opencode-update.lock");
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  try {
    mkdirSync(file);
  } catch {
    try {
      if (Date.now() - statSync(file).mtimeMs < LOCK_STALE) return undefined;
      rmSync(file, { recursive: true, force: true });
      mkdirSync(file);
    } catch {
      return undefined;
    }
  }
  return () => rmSync(file, { recursive: true, force: true });
}

async function fetchLimited(fetchImpl, url, limit, accept) {
  const res = await fetchImpl(url, { headers: { accept }, redirect: "error", signal: AbortSignal.timeout(60_000) });
  if (!res.ok) throw new Error(`HTTP ${res.status} from ${new URL(url).host}`);
  const body = Buffer.from(await res.arrayBuffer());
  if (body.length > limit) throw new Error(`response from ${new URL(url).host} is too large`);
  return body;
}

/** The files of an npm tarball (`package/...`), refusing anything but regular files and folders inside it. */
export function untar(gzipped) {
  const data = gunzipSync(gzipped);
  const files = new Map();
  let longPath;
  const field = (block, start, length) => block.subarray(start, start + length).toString("utf8").replace(/\0.*$/s, "");
  for (let offset = 0; offset + 512 <= data.length;) {
    const header = data.subarray(offset, offset + 512);
    if (header.every((b) => b === 0)) break;
    const size = Number.parseInt(field(header, 124, 12).trim() || "0", 8);
    const type = String.fromCharCode(header[156] || 48);
    const mode = Number.parseInt(field(header, 100, 8).trim() || "644", 8);
    const body = data.subarray(offset + 512, offset + 512 + size);
    offset += 512 + Math.ceil(size / 512) * 512;
    if (type === "x") {
      const match = /\d+ path=([^\n]*)\n/.exec(body.toString("utf8"));
      longPath = match?.[1];
      continue;
    }
    if (type === "g") continue;
    const prefix = field(header, 345, 155);
    const name = longPath ?? (prefix ? `${prefix}/${field(header, 0, 100)}` : field(header, 0, 100));
    longPath = undefined;
    if (type === "5") continue;
    if (type !== "0" && type !== "\0") throw new Error(`unsupported entry in the package: ${name}`);
    const parts = name.split("/");
    if (parts[0] !== "package" || parts.length < 2 || parts.some((p) => p === "" || p === "." || p === "..") || name.includes("\\")) {
      throw new Error(`unsafe path in the package: ${name}`);
    }
    files.set(parts.slice(1).join("/"), { data: Buffer.from(body), executable: (mode & 0o111) !== 0 });
  }
  return files;
}

function writeTree(dir, files) {
  for (const [name, file] of files) {
    const target = path.join(dir, name);
    mkdirSync(path.dirname(target), { recursive: true });
    writeFileSync(target, file.data);
    chmodSync(target, file.executable ? 0o755 : 0o644);
  }
}

/** Loads a staged copy with updates and logging off and checks that it adds the Egbe connector. */
async function smokeTest(dir, expectedUrl) {
  const { default: plugin } = await import(`${pathToFileURL(path.join(dir, "index.js")).href}?verify=${Date.now()}`);
  if (plugin?.id !== "egbe" || typeof plugin.server !== "function" || typeof plugin.setup !== "function") {
    throw new Error("the new version does not export the plugin");
  }
  const client = { session: { messages: async () => ({ data: [] }) } };
  const hooks = await plugin.server({ client, directory: dir, worktree: dir }, { autoUpdate: false, sessionLogging: false });
  const config = {};
  await hooks.config(config);
  await hooks.dispose?.();
  if (config.mcp?.egbe?.url !== expectedUrl) throw new Error("the new version does not add the Egbe connector");
}

/** Downloads, verifies and stages `version`; returns the staged folder. */
async function stage({ registry, packument, version, capabilities, stagingDir, fetchImpl, mcpUrl }) {
  const manifest = packument.versions?.[version];
  if (manifest?.name !== PACKAGE || manifest.version !== version) throw new Error(`the registry has no ${PACKAGE}@${version}`);
  const integrity = String(manifest.dist?.integrity ?? "");
  if (!integrity.startsWith("sha512-")) throw new Error("the registry gives no SHA-512 integrity");
  const tarball = new URL(manifest.dist.tarball);
  if (tarball.origin !== new URL(registry).origin) throw new Error(`the tarball is not on ${new URL(registry).host}`);
  const gzipped = await fetchLimited(fetchImpl, tarball.href, MAX_TARBALL, "application/octet-stream");
  const digest = `sha512-${createHash("sha512").update(gzipped).digest("base64")}`;
  if (digest !== integrity) throw new Error("the tarball does not match the registry's integrity");
  const files = untar(gzipped);
  const pkg = JSON.parse(files.get("package.json")?.data.toString("utf8") ?? "null");
  if (pkg?.name !== PACKAGE || pkg.version !== version) throw new Error("the tarball's package.json names another package or version");
  if (!sameCapabilities(pkg.egbe?.capabilities, capabilities)) throw new Error("the tarball declares other capabilities than the registry");
  rmSync(stagingDir, { recursive: true, force: true });
  try {
    writeTree(stagingDir, files);
    await smokeTest(stagingDir, mcpUrl);
  } catch (error) {
    rmSync(stagingDir, { recursive: true, force: true });
    throw error;
  }
  return stagingDir;
}

function installedVersion(packageDir) {
  try {
    const version = JSON.parse(readFileSync(path.join(packageDir, "package.json"), "utf8")).version;
    return typeof version === "string" ? version : null;
  } catch {
    return null;
  }
}

function runCli(command, args, cwd) {
  return new Promise((resolve) => {
    let child;
    try {
      child = spawn(command, args, { cwd, stdio: "ignore", windowsHide: true });
    } catch (error) {
      resolve({ code: -1, error: error.message });
      return;
    }
    const timer = setTimeout(() => child.kill(), 5 * 60 * 1000);
    child.on("error", (error) => { clearTimeout(timer); resolve({ code: -1, error: error.message }); });
    child.on("exit", (code) => { clearTimeout(timer); resolve({ code }); });
  });
}

/** Records that this version loaded after an update and removes the copy kept for rollback. */
export function confirmLoaded(version, environment = process.env) {
  const update = readState(environment).update;
  if (update?.status !== "installed" || update.to !== version) return false;
  if (update.previous) rmSync(update.previous, { recursive: true, force: true });
  writeState({ update: { ...update, status: "applied", appliedAt: new Date().toISOString(), previous: undefined } }, environment);
  return true;
}

/**
 * One update check. `install` is v1Install's or v2Install's result (or a function
 * returning one); returns a short result, which is also recorded in the state file.
 */
export async function checkForUpdate({
  version, capabilities, install, settings, fetchImpl = fetch, cli = runCli, opencode = process.execPath, cwd,
  environment = process.env, mcpUrl = "https://os.hz.egbe.dev/mcp",
}) {
  const record = (fields) => {
    const update = { ...readState(environment).update, checkedAt: new Date().toISOString(), running: version, ...fields };
    writeState({ update }, environment);
    return fields.result;
  };
  confirmLoaded(version, environment);
  if (!settings.enabled) return record({ result: `off: ${settings.error ?? "autoUpdate is false"}` });
  const where = typeof install === "function" ? await install() : install;
  if (where.kind === "folder") return record({ result: "skipped: installed from a folder; update it with git pull" });
  if (where.kind === "pinned") return record({ result: `skipped: pinned to ${where.spec}` });
  if (where.kind !== "npm") return record({ result: "skipped: install not recognized" });
  const release = lock(stateDir(environment));
  if (!release) return record({ result: "skipped: another update is running" });
  let staged;
  try {
    const packument = JSON.parse((await fetchLimited(fetchImpl, `${settings.registry}/${PACKAGE.replace("/", "%2f")}`,
      MAX_PACKUMENT, "application/json")).toString("utf8"));
    const latest = packument["dist-tags"]?.latest;
    if (typeof latest !== "string" || compareVersions(latest, version) <= 0) return record({ result: "current", latest });
    // OpenCode 1.x loads a swapped-in copy only at its next start; until then this process
    // runs the old version, so the copy on disk, not the running one, says what is installed.
    const onDisk = where.packageDir ? installedVersion(where.packageDir) : null;
    if (onDisk && compareVersions(latest, onDisk) <= 0) {
      return record({ result: `installed ${onDisk}; OpenCode loads it at its next start`, latest });
    }
    const declared = packument.versions?.[latest]?.egbe?.capabilities;
    if (!sameCapabilities(declared, capabilities)) {
      return record({
        result: `manual: ${latest} changes the plugin's capabilities; update it by hand`, latest, status: "manual",
      });
    }
    if (where.packageDir) {
      // OpenCode 1.x: stage beside OpenCode's copy, so the swap is a rename on one disk.
      const scope = path.dirname(where.packageDir);
      const suffix = randomBytes(4).toString("hex");
      staged = await stage({ registry: settings.registry, packument, version: latest, capabilities, fetchImpl, mcpUrl,
        stagingDir: path.join(scope, `.opencode-${latest}-${suffix}`) });
      // A copy swapped in earlier that OpenCode hasn't loaded yet is replaced; the rollback copy
      // stays the version that actually runs, so it is kept and stays tracked.
      const pending = readState(environment).update;
      // The rollback copy stays recorded until the new version loads, even if a check failed meanwhile.
      const keep = onDisk && compareVersions(onDisk, version) > 0 && pending?.previous
        && existsSync(pending.previous) ? pending.previous : null;
      const previous = keep ?? path.join(scope, `.opencode-previous-${version}-${suffix}`);
      const displaced = keep ? path.join(scope, `.opencode-unloaded-${onDisk}-${suffix}`) : previous;
      renameSync(where.packageDir, displaced);
      try {
        renameSync(staged, where.packageDir);
      } catch (error) {
        renameSync(displaced, where.packageDir);
        throw error;
      }
      staged = undefined;
      if (keep) rmSync(displaced, { recursive: true, force: true });
      return record({ result: `installed ${latest}; OpenCode loads it at its next start`, latest, status: "installed",
        from: version, to: latest, previous, at: new Date().toISOString() });
    }
    // OpenCode 2.x: verify the same way, then let OpenCode install it with its own npm installer.
    staged = await stage({ registry: settings.registry, packument, version: latest, capabilities, fetchImpl, mcpUrl,
      stagingDir: path.join(stateDir(environment), `opencode-staging-${randomBytes(4).toString("hex")}`) });
    const run = await cli(opencode, ["plugin", "update", where.target], cwd);
    if (run.code !== 0) {
      return record({ result: `failed: opencode plugin update exited with ${run.code}${run.error ? ` (${run.error})` : ""}`,
        latest, status: "failed" });
    }
    return record({ result: `installed ${latest} through opencode plugin update`, latest, status: "installed",
      from: version, to: latest, at: new Date().toISOString() });
  } catch (error) {
    return record({ result: `failed: ${error?.message ?? error}`, status: "failed" });
  } finally {
    if (staged) rmSync(staged, { recursive: true, force: true });
    release();
  }
}

/** Runs checks a while after loading and then periodically; timers never keep OpenCode alive. */
export function scheduleUpdates({ settings, check, setTimer = setTimeout, setRepeat = setInterval }) {
  if (!settings.enabled) return () => {};
  let running = false;
  const run = async () => {
    if (running) return;
    running = true;
    try {
      await check();
    } catch {
      // checkForUpdate records its own failures.
    } finally {
      running = false;
    }
  };
  let repeat;
  const first = setTimer(() => {
    void run();
    repeat = setRepeat(run, settings.intervalMs);
    repeat?.unref?.();
  }, settings.initialDelayMs);
  first?.unref?.();
  return () => {
    clearTimeout(first);
    if (repeat) clearInterval(repeat);
  };
}

