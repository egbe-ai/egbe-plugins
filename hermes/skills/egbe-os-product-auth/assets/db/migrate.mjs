#!/usr/bin/env node
// Idempotent, concurrency-safe migration runner for the attached Postgres.
//
// Applies db/migrations/*.sql in filename order, once each, inside a transaction,
// guarded by a Postgres advisory lock so parallel boots/deploys can't race. Run
// it during a controlled build/deploy step (e.g. `npm run db:migrate`), NEVER
// from a public route. Requires DATABASE_URL. Safe to run repeatedly.
//
// Only dependency is `pg` (already needed to talk to the attached Postgres).
import { readdir, readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import pg from "pg";

const LOCK_KEY = 776352; // fixed key: every runner of this app takes the same lock
const migrationsDir = join(dirname(fileURLToPath(import.meta.url)), "migrations");

async function main() {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) throw new Error("DATABASE_URL is not set");

  const client = new pg.Client({ connectionString });
  await client.connect();
  let locked = false;
  try {
    await client.query("select pg_advisory_lock($1)", [LOCK_KEY]);
    locked = true;

    await client.query(
      `create table if not exists schema_migrations (
         name text primary key,
         applied_at timestamptz not null default now()
       )`,
    );

    const files = (await readdir(migrationsDir)).filter((f) => f.endsWith(".sql")).sort();
    for (const name of files) {
      const applied = await client.query("select 1 from schema_migrations where name = $1", [name]);
      if (applied.rowCount) {
        console.log(`skip    ${name}`);
        continue;
      }
      const sql = await readFile(join(migrationsDir, name), "utf8");
      await client.query("begin");
      try {
        await client.query(sql);
        await client.query("insert into schema_migrations(name) values ($1)", [name]);
        await client.query("commit");
        console.log(`applied ${name}`);
      } catch (err) {
        await client.query("rollback");
        throw err;
      }
    }
  } finally {
    if (locked) await client.query("select pg_advisory_unlock($1)", [LOCK_KEY]).catch(() => {});
    await client.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
