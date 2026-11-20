// Egbe's native OpenCode plugin, published from egbe-ai/claw-swarm plugins/opencode
// as the npm package @egbe/opencode (and under plugins/egbe-opencode/ of
// egbe-ai/egbe-plugins). index.js exports only its default, which plugin loaders read.
//
// One default export serves both plugin APIs, as OpenCode's V1 migration guide
// describes: OpenCode 1.x (1.18.29 and later) calls `server()`, OpenCode 2.x
// calls `setup()`. Either way the plugin
//   - adds the Egbe MCP server (`egbe`, remote, signed in with OpenCode's own MCP
//     OAuth and Dashboard's dynamic client registration) unless the founder's
//     configuration already defines one;
//   - adds Egbe's skills bundled in this package's `skills/` folder;
//   - logs each run of a session in a project folder set up for Egbe to Egbe's
//     telemetry gateway (session-log.js);
//   - updates itself from npm (update.js).
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  GATEWAY, OS_URL, lastTurnId, loggingSettings, projectFolder, sendTurn, stepsFromV1, stepsFromV2, turnTraces,
} from "./session-log.js";
import { statePath, writeState } from "./state.js";
import { checkForUpdate, scheduleUpdates, updaterSettings, v1Install, v2Install } from "./update.js";

export const PLUGIN_ID = "egbe";
export const MCP_NAME = "egbe";
const MODULE_ROOT = path.dirname(fileURLToPath(import.meta.url));
const PACKAGE_JSON = JSON.parse(readFileSync(path.join(MODULE_ROOT, "package.json"), "utf8"));
export const VERSION = PACKAGE_JSON.version;
// What an update may not change without the founder: see update.js.
export const CAPABILITIES = PACKAGE_JSON.egbe?.capabilities;
export const SKILLS_DIR = path.join(MODULE_ROOT, "skills");
// OpenCode 2.x events that end a run of a session.
export const RUN_ENDED = ["session.execution.succeeded", "session.execution.failed", "session.execution.interrupted"];

export { statePath };

function recordResult(entry) {
  writeState({ lastSessionLog: entry });
}

/** The telemetry gateway: Egbe's, or a loopback test gateway named in the plugin options. */
export function gatewayUrl(options) {
  const raw = options?.telemetryUrl;
  if (raw === undefined) return GATEWAY;
  const url = new URL(String(raw));
  const loopback = url.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
  if (url.href.replace(/\/$/, "") !== GATEWAY && !loopback) throw new Error("telemetryUrl must be Egbe's gateway or a loopback test gateway");
  return url.href.replace(/\/$/, "");
}

function frontmatter(content) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(content);
  if (!match) return undefined;
  const fields = {};
  for (const line of match[1].split(/\r?\n/)) {
    const field = /^(name|description):\s*(.*)$/.exec(line);
    if (field) fields[field[1]] = field[2].trim().replace(/^"(.*)"$/, "$1").replace(/^'(.*)'$/, "$1");
  }
  return { fields, body: content.slice(match[0].length) };
}

/** The bundled skills as OpenCode 2.x `Skill.Info` entries (one level under `skills/`). */
export function bundledSkills(dir = SKILLS_DIR) {
  let names;
  try {
    names = readdirSync(dir, { withFileTypes: true }).filter((e) => e.isDirectory() && !e.name.startsWith(".")).map((e) => e.name);
  } catch {
    return [];
  }
  const skills = [];
  for (const name of names.sort()) {
    const file = path.join(dir, name, "SKILL.md");
    let parsed;
    try {
      parsed = frontmatter(readFileSync(file, "utf8"));
    } catch {
      continue;
    }
    if (!parsed) continue;
    skills.push({
      id: name, name: parsed.fields.name || name,
      ...(parsed.fields.description ? { description: parsed.fields.description } : {}),
      path: file, content: parsed.body,
    });
  }
  return skills;
}

/** Adds the Egbe MCP server and the bundled skills to an OpenCode 1.x configuration. */
export function configureV1(config, skillsDir = SKILLS_DIR) {
  config.mcp ??= {};
  // A server the founder configured, such as one with a business key, stays as it is.
  if (!config.mcp[MCP_NAME]) config.mcp[MCP_NAME] = { type: "remote", url: `${OS_URL}/mcp` };
  if (bundledSkills(skillsDir).length) {
    config.skills ??= {};
    config.skills.paths ??= [];
    if (!config.skills.paths.includes(skillsDir)) config.skills.paths.push(skillsDir);
  }
  return config;
}

// Code Mode off: Egbe's skills name the connector's tools, so they stay on the native tool list.
export const MCP_V2 = { type: "remote", url: `${OS_URL}/mcp`, codemode: false };

/** Logs the last turn of a session once its run ends; never throws. */
export function sessionLogger({ api, options, root, readSteps, fetchImpl, record = recordResult }) {
  const sent = new Map();
  const running = new Map();
  const publicKeys = new Map();
  async function log(sessionID, directory) {
    const folder = projectFolder(directory, root);
    let result;
    try {
      const settings = loggingSettings(folder, options);
      if (settings.off) {
        result = `off: ${settings.off}`;
      } else {
        const steps = await readSteps(sessionID);
        const turn = lastTurnId(steps);
        if (turn !== undefined && sent.get(sessionID) === turn) return;
        const body = turnTraces({ steps, sessionID, workspace: folder, version: VERSION, api });
        if (!body) {
          result = "skipped: no founder message in the run";
        } else {
          result = await sendTurn({ settings, body, publicKeyCache: publicKeys, gateway: gatewayUrl(options),
            ...(fetchImpl ? { fetchImpl } : {}) });
          if (result === "sent") sent.set(sessionID, turn);
        }
      }
    } catch (error) {
      result = `failed: ${error?.message ?? error}`;
    }
    record({ at: new Date().toISOString(), result, session: sessionID, workspace: folder ? path.basename(folder) : "" });
    return result;
  }
  return {
    /** Both `session.status` (idle) and the older `session.idle` may announce one end: runs coalesce. */
    idle(sessionID, directory) {
      if (typeof sessionID !== "string" || !sessionID) return Promise.resolve();
      const previous = running.get(sessionID) ?? Promise.resolve();
      const next = previous.then(() => log(sessionID, directory));
      running.set(sessionID, next);
      return next.finally(() => {
        if (running.get(sessionID) === next) running.delete(sessionID);
      });
    },
    /** Waits, for at most `limit` ms, for runs being logged, so a short-lived `opencode run` still sends its turn. */
    async flush(limit = 15_000) {
      let timer;
      const timeout = new Promise((resolve) => { timer = setTimeout(resolve, limit); });
      await Promise.race([Promise.allSettled([...running.values()]), timeout]);
      clearTimeout(timer);
    },
  };
}

/** OpenCode 1.x: returns the hooks object. */
export async function server(input, options) {
  const settings = updaterSettings(options);
  const stopUpdates = scheduleUpdates({
    settings,
    check: () => checkForUpdate({ version: VERSION, capabilities: CAPABILITIES, install: v1Install(MODULE_ROOT), settings,
      cwd: input?.directory }),
  });
  const logger = sessionLogger({
    api: "v1", options, root: input?.worktree,
    readSteps: async (id) => {
      const res = await input.client.session.messages({ path: { id }, query: { directory: input.directory } });
      return stepsFromV1(res?.data ?? res);
    },
  });
  return {
    async config(config) {
      configureV1(config);
    },
    async event({ event }) {
      const idle = event?.type === "session.idle" || (event?.type === "session.status" && event.properties?.status?.type === "idle");
      if (idle) await logger.idle(event.properties?.sessionID, input?.directory);
    },
    async dispose() {
      stopUpdates();
      await logger.flush();
    },
  };
}

/** OpenCode 2.x: registers transforms and the session-logging subscription. */
export async function setup(ctx) {
  await ctx.mcp.transform((editor) => {
    if (!editor.get(MCP_NAME)) editor.set(MCP_NAME, MCP_V2);
  });
  const skills = bundledSkills();
  if (skills.length) {
    await ctx.skill.transform((editor) => {
      // A project's own installed copy of a skill wins over the plugin's.
      for (const skill of skills) if (!editor.get(skill.id)) editor.add(skill);
    });
  }
  const here = ctx.location?.directory;
  const logger = sessionLogger({
    api: "v2", options: ctx.options, root: ctx.location?.project?.directory,
    readSteps: async (sessionID) => stepsFromV2(await ctx.session.context({ sessionID })),
  });
  const settings = updaterSettings(ctx.options);
  const stopUpdates = scheduleUpdates({
    settings,
    check: () => checkForUpdate({ version: VERSION, capabilities: CAPABILITIES, settings, cwd: here,
      install: async () => v2Install(await ctx.plugin.list({ location: here ? { directory: here } : undefined })) }),
  });
  const controller = new AbortController();
  void (async () => {
    try {
      for await (const event of ctx.event.subscribe({ types: RUN_ENDED, signal: controller.signal })) {
        // Each plugin instance logs only its own location's sessions.
        const where = event?.location?.directory;
        if (where && here && where !== here) continue;
        await logger.idle(event?.data?.sessionID, where ?? here);
      }
    } catch {
      // The stream ends when the plugin unloads.
    }
  })();
  return async () => {
    stopUpdates();
    controller.abort();
    await logger.flush();
  };
}

export default { id: PLUGIN_ID, setup, server };
