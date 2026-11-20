// The plugin's state file: the last session-logging result and the updater's
// state, for the founder and the agent to check. It never holds a secret.
import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

export function stateDir(environment = process.env) {
  const base = environment.XDG_STATE_HOME || path.join(os.homedir(), ".local", "state");
  return path.join(base, "egbe");
}

export function statePath(environment = process.env) {
  return path.join(stateDir(environment), "opencode-plugin.json");
}

export function readState(environment = process.env) {
  try {
    const value = JSON.parse(readFileSync(statePath(environment), "utf8"));
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

/** Merges `patch` into the state file; never throws, since the file is only informational. */
export function writeState(patch, environment = process.env) {
  try {
    const file = statePath(environment);
    mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
    const next = { ...readState(environment), ...patch };
    const temporary = `${file}.${process.pid}.tmp`;
    writeFileSync(temporary, JSON.stringify(next, null, 2) + "\n", { mode: 0o600 });
    renameSync(temporary, file);
  } catch {
    // Informational only.
  }
}
