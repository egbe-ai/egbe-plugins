const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");
const { updateQueue } = require("./reply-queue");

const tmpRun = () => fs.mkdtempSync(path.join(os.tmpdir(), "reply-queue-"));

test("parallel writers lose no update", async () => {
  const runDir = tmpRun();
  const writer = (id) =>
    new Promise((resolve, reject) => {
      const code = `require(${JSON.stringify(path.join(__dirname, "reply-queue"))}).updateQueue(${JSON.stringify(runDir)}, (q) => { q.push({ email_id: ${JSON.stringify(id)} }); })`;
      const child = spawn(process.execPath, ["-e", code], { stdio: "inherit" });
      child.on("exit", (c) =>
        c === 0 ? resolve() : reject(new Error(`writer ${id} exited ${c}`)),
      );
    });
  await Promise.all(Array.from({ length: 8 }, (_, i) => writer(`m${i}`)));
  const queue = JSON.parse(
    fs.readFileSync(path.join(runDir, "reply-queue.json"), "utf8"),
  );
  assert.deepStrictEqual(queue.map((q) => q.email_id).sort(), [
    "m0",
    "m1",
    "m2",
    "m3",
    "m4",
    "m5",
    "m6",
    "m7",
  ]);
  assert.deepStrictEqual(fs.readdirSync(runDir).sort(), ["reply-queue.json"]);
});

test("a held lock makes the writer wait, then fail without writing", () => {
  const runDir = tmpRun();
  fs.mkdirSync(path.join(runDir, ".reply-queue.lock"));
  assert.throws(
    () =>
      updateQueue(runDir, (q) => q.push({ email_id: "x" }), { waitMs: 300 }),
    /locked/,
  );
  assert.ok(!fs.existsSync(path.join(runDir, "reply-queue.json")));
});

test("a lock left by a killed process is taken over", () => {
  const runDir = tmpRun();
  const lock = path.join(runDir, ".reply-queue.lock");
  fs.mkdirSync(lock);
  const old = new Date(Date.now() - 11 * 60 * 1000);
  fs.utimesSync(lock, old, old);
  updateQueue(runDir, (q) => q.push({ email_id: "x" }), { waitMs: 300 });
  assert.strictEqual(
    JSON.parse(fs.readFileSync(path.join(runDir, "reply-queue.json"), "utf8"))
      .length,
    1,
  );
  assert.ok(!fs.existsSync(lock));
});

test("a failed change writes nothing and releases the lock", () => {
  const runDir = tmpRun();
  assert.throws(
    () =>
      updateQueue(runDir, () => {
        throw new Error("refused");
      }),
    /refused/,
  );
  assert.ok(!fs.existsSync(path.join(runDir, "reply-queue.json")));
  assert.ok(!fs.existsSync(path.join(runDir, ".reply-queue.lock")));
});
