#!/usr/bin/env node
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import pg from "pg";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const catalogPath = resolve(root, "src/lib/egbe-billing/plans.json");

function requiredEnv(name) {
  const value = String(process.env[name] || "").trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
}

export function validateCatalog(value) {
  if (!value || value.catalog_version !== 1 || !Array.isArray(value.plans)) {
    throw new Error("Billing plan catalog is invalid");
  }
  const appSlug = String(value.app_slug || "").trim();
  if (!/^[a-z0-9][a-z0-9-]{0,62}$/.test(appSlug)) {
    throw new Error("Billing catalog app_slug must match the deployed product slug");
  }
  const keys = new Set();
  const paid = [];
  for (const plan of value.plans) {
    const planKey = String(plan.plan_key || "").trim();
    if (!/^[a-z][a-z0-9_-]{1,63}$/.test(planKey) || keys.has(planKey)) {
      throw new Error(`Invalid or duplicate plan_key: ${planKey}`);
    }
    keys.add(planKey);
    if ("provider_product_id" in plan || "provider_price_id" in plan) {
      throw new Error(`Plan ${planKey} must not contain provider ids`);
    }
    if (!String(plan.display_name || "").trim() || !String(plan.summary || "").trim()) {
      throw new Error(`Plan ${planKey} requires display_name and summary`);
    }
    if (!/^[a-z]{3}$/.test(String(plan.currency || "")) || typeof plan.selectable !== "boolean") {
      throw new Error(`Plan ${planKey} has an invalid commercial contract`);
    }
    if (!Array.isArray(plan.entitlements) || plan.entitlements.some((item) => typeof item !== "string" || !item.trim())) {
      throw new Error(`Plan ${planKey} has invalid entitlements`);
    }
    if (new Set(plan.entitlements).size !== plan.entitlements.length) {
      throw new Error(`Plan ${planKey} has duplicate entitlements`);
    }
    if (plan.kind === "subscription") {
      if (!Number.isInteger(plan.amount_cents) || plan.amount_cents < 1) {
        throw new Error(`Plan ${planKey} has invalid amount_cents`);
      }
      if (!new Set(["month", "year"]).has(plan.interval)) {
        throw new Error(`Plan ${planKey} has invalid subscription interval`);
      }
      paid.push(plan);
    } else if (plan.kind !== "free") {
      throw new Error(`Plan ${planKey} must be free or subscription`);
    } else if (plan.amount_cents !== 0 || plan.interval !== null) {
      throw new Error(`Free plan ${planKey} must have zero amount and no interval`);
    }
  }
  if (!keys.has("free")) throw new Error("Billing catalog must define the free plan");
  if (!paid.length) throw new Error("Billing catalog must define at least one subscription plan");
  return { appSlug, paid };
}

async function osRequest(baseUrl, apiKey, path, { body, idempotencyKey } = {}) {
  const response = await fetch(`${baseUrl}/payments${path}`, {
    method: body ? "POST" : "GET",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const envelope = await response.json().catch(() => null);
  if (!response.ok || !envelope || envelope.code >= 400) {
    throw new Error(envelope?.message || `Egbe Payments returned HTTP ${response.status}`);
  }
  return envelope.data;
}

export function metadataFor(appSlug, planKey) {
  return {
    plan_key: planKey,
    payment_gateway_app_slug: appSlug,
    payment_gateway_webhook_path: "/api/payments/webhook",
  };
}

async function main() {
  const source = await readFile(catalogPath, "utf8");
  const catalog = JSON.parse(source);
  const { appSlug, paid } = validateCatalog(catalog);
  const baseUrl = requiredEnv("OS_URL").replace(/\/$/, "");
  const apiKey = requiredEnv("OS_API_KEY");
  const databaseUrl = requiredEnv("DATABASE_URL");
  const digest = createHash("sha256").update(source).digest("hex");
  const bindings = [];
  for (const plan of paid) {
    const metadata = metadataFor(appSlug, plan.plan_key);
    const product = await osRequest(baseUrl, apiKey, "/products", {
      idempotencyKey: `catalog:${appSlug}:${plan.plan_key}:product:v1`,
      body: { name: plan.display_name, description: plan.summary, metadata },
    });
    if (!product?.id) throw new Error(`No provider product returned for ${plan.plan_key}`);
    const price = await osRequest(baseUrl, apiKey, "/prices", {
      idempotencyKey: `catalog:${appSlug}:${plan.plan_key}:price:${plan.amount_cents}:${plan.currency}:${plan.interval}`,
      body: {
        product: product.id,
        unit_amount: plan.amount_cents,
        currency: plan.currency,
        recurring_interval: plan.interval,
        metadata,
      },
    });
    if (!price?.id) throw new Error(`No provider price returned for ${plan.plan_key}`);
    bindings.push({ planKey: plan.plan_key, productId: product.id, priceId: price.id });
  }
  const evidence = await osRequest(baseUrl, apiKey, "/evidence");
  const productIds = new Set((evidence?.products || []).map((item) => item.id));
  const priceIds = new Set((evidence?.prices || []).map((item) => item.id));
  for (const binding of bindings) {
    if (!productIds.has(binding.productId) || !priceIds.has(binding.priceId)) {
      throw new Error(`Provider readback is incomplete for ${binding.planKey}`);
    }
  }
  const client = new pg.Client({ connectionString: databaseUrl });
  await client.connect();
  try {
    await client.query("begin");
    for (const binding of bindings) {
      await client.query(
        `insert into billing_provider_bindings (
           plan_key, provider_product_id, provider_price_id, catalog_digest
         ) values ($1, $2, $3, $4)
         on conflict (plan_key) do update set
           provider_product_id = excluded.provider_product_id,
           provider_price_id = excluded.provider_price_id,
           catalog_digest = excluded.catalog_digest,
           synced_at = now()`,
        [binding.planKey, binding.productId, binding.priceId, digest],
      );
    }
    await client.query("commit");
  } catch (error) {
    await client.query("rollback").catch(() => undefined);
    throw error;
  } finally {
    await client.end();
  }
  process.stdout.write(`${JSON.stringify({ ok: true, plans_synced: bindings.length })}\n`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`billing:sync failed: ${String(error?.message || error)}\n`);
    process.exitCode = 1;
  });
}
