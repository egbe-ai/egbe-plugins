import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const productRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");

async function source(path) {
  return readFile(resolve(productRoot, path), "utf8");
}

test("concurrent checkout requests converge on one active logical attempt", async () => {
  const [migration, repository] = await Promise.all([
    source("db/migrations/1000_egbe_billing.sql"),
    source("src/lib/egbe-billing/repository.ts"),
  ]);
  const activePredicate = /where status in \('pending', 'created'\)/i;
  assert.match(migration, /unique index[\s\S]+\(account_id, plan_key\)/i);
  assert.match(migration, activePredicate);
  assert.match(repository, /on conflict \(account_id, plan_key\)/i);
  assert.match(repository, activePredicate);
  assert.match(repository, /idempotency_key/i);
});

test("lifecycle persistence records ordering, duplicates, and multiple capabilities", async () => {
  const migration = await source("db/migrations/1000_egbe_billing.sql");
  assert.match(migration, /processed_payment_events[\s\S]+event_id\s+text primary key/i);
  assert.match(migration, /last_event_created\s+bigint not null/i);
  assert.match(migration, /unique \(account_id, capability, source\)/i);
});

test("billing surface and runtime marker keep account and secret boundaries explicit", async () => {
  const [page, marker] = await Promise.all([
    source("src/app/account/billing/page.tsx"),
    source(".egbe/scaffolds/billing-nextjs-subscription.v1.json"),
  ]);
  assert.match(page, /requireProductAccount/);
  const contract = JSON.parse(marker);
  assert.deepEqual(contract.requires_runtime_env, [
    "DATABASE_URL",
    "OS_URL",
    "OS_API_KEY",
    "EGBE_PAYMENT_WEBHOOK_SECRET",
  ]);
});

test("checkout enables customer codes by default and bounds automatic discounts", async () => {
  const [builder, client] = await Promise.all([
    source("src/lib/egbe-billing/checkout-payload.ts"),
    source("src/lib/egbe-billing/os-client.ts"),
  ]);
  assert.match(builder, /allowPromotionCodes \?\? true/);
  assert.match(builder, /discount \? false/);
  assert.match(builder, /discounts: \[discount\]/);
  assert.match(client, /discounts\?: \[CheckoutDiscount\]/);
  assert.match(client, /\{ coupon: string \}/);
  assert.match(client, /\{ promotion_code: string \}/);
});
