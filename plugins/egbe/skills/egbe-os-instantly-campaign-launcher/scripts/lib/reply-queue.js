// reply-queue.json is shared by reply-worker.js (adds items) and send-reply.js
// (changes their status). Every change goes through updateQueue: one writer at
// a time (a lock directory next to the file) and an atomic replace, so two
// processes cannot overwrite each other's updates.
const fs = require("fs");
const path = require("path");

const STALE_LOCK_MS = 10 * 60 * 1000;

function pause(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function updateQueue(runDir, change, { waitMs = 30000 } = {}) {
  const file = path.join(runDir, "reply-queue.json");
  const lock = path.join(runDir, ".reply-queue.lock");
  const deadline = Date.now() + waitMs;
  for (;;) {
    try {
      fs.mkdirSync(lock);
      break;
    } catch (err) {
      if (err.code !== "EEXIST") throw err;
      let age = 0;
      try {
        age = Date.now() - fs.statSync(lock).mtimeMs;
      } catch {}
      // A holder never keeps the lock longer than one read-modify-write; a
      // lock this old was left by a killed process.
      if (age > STALE_LOCK_MS) {
        // Rename first: only one waiter can move the stale lock away, so two
        // waiters cannot both remove it and enter together.
        const moved = `${lock}.stale.${process.pid}.${Date.now()}`;
        try {
          fs.renameSync(lock, moved);
          // Another waiter may have replaced the stale lock with its own in
          // the meantime; a fresh one goes back where it was.
          if (Date.now() - fs.statSync(moved).mtimeMs <= STALE_LOCK_MS) {
            fs.renameSync(moved, lock);
          } else {
            fs.rmSync(moved, { recursive: true, force: true });
          }
        } catch (renameErr) {
          if (renameErr.code !== "ENOENT") throw renameErr;
        }
        continue;
      }
      if (Date.now() > deadline)
        throw new Error(`Reply queue is locked by another process: ${lock}`);
      pause(200);
    }
  }
  try {
    const queue = fs.existsSync(file)
      ? JSON.parse(fs.readFileSync(file, "utf8"))
      : [];
    const result = change(queue);
    const tmp = `${file}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(queue, null, 2) + "\n");
    fs.renameSync(tmp, file);
    return result;
  } finally {
    fs.rmSync(lock, { recursive: true, force: true });
  }
}

module.exports = { updateQueue };
