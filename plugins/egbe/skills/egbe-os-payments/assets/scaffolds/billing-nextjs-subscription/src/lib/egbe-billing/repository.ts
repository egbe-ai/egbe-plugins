import "server-only";

import type { PoolClient } from "pg";

import { productDatabase, queryProductDatabase } from "@/lib/egbe-product";

import { billingPlan } from "./catalog";
import { shouldApplyPaymentEvent } from "./lifecycle.mjs";

export type BillingState = {
  accountId: string;
  planKey: string;
  status: "free" | "trialing" | "active" | "past_due" | "canceling" | "paused" | "canceled";
  customerId: string | null;
  subscriptionId: string | null;
  priceId: string | null;
  currentPeriodEnd: Date | null;
  cancelAtPeriodEnd: boolean;
  lastEventCreated: number;
};

export type BillingEvent = {
  id: string;
  type: string;
  created: number;
  data?: { object?: Record<string, unknown> };
  livemode?: boolean;
};

export type CheckoutAttempt = {
  id: string;
  idempotencyKey: string;
  planKey: string;
  returnPath: string;
  attribution: Record<string, unknown>;
};

export type BillingTransition = {
  subscription_status: BillingState["status"];
  access: "grant" | "preserve" | "revoke";
  plan_key?: string | null;
  customer_id?: string | null;
  subscription_id?: string | null;
  price_id?: string | null;
  current_period_end?: string | null;
  cancel_at_period_end?: boolean;
};

const FREE_STATE = (accountId: string): BillingState => ({
  accountId,
  planKey: "free",
  status: "free",
  customerId: null,
  subscriptionId: null,
  priceId: null,
  currentPeriodEnd: null,
  cancelAtPeriodEnd: false,
  lastEventCreated: 0,
});

export async function readBillingState(accountId: string): Promise<BillingState> {
  const result = await queryProductDatabase<{
    account_id: string;
    plan_key: string;
    subscription_status: BillingState["status"];
    provider_customer_id: string | null;
    provider_subscription_id: string | null;
    provider_price_id: string | null;
    current_period_end: Date | null;
    cancel_at_period_end: boolean;
    last_event_created: string | number;
  }>("select * from account_billing where account_id = $1", [accountId]);
  const row = result.rows[0];
  if (!row) return FREE_STATE(accountId);
  return {
    accountId: row.account_id,
    planKey: row.plan_key,
    status: row.subscription_status,
    customerId: row.provider_customer_id,
    subscriptionId: row.provider_subscription_id,
    priceId: row.provider_price_id,
    currentPeriodEnd: row.current_period_end,
    cancelAtPeriodEnd: row.cancel_at_period_end,
    lastEventCreated: Number(row.last_event_created),
  };
}

export async function providerPriceForPlan(planKey: string): Promise<string> {
  const result = await queryProductDatabase<{ provider_price_id: string }>(
    "select provider_price_id from billing_provider_bindings where plan_key = $1",
    [planKey],
  );
  const priceId = result.rows[0]?.provider_price_id;
  if (!priceId) throw new Error(`Billing plan ${planKey} has not been synchronized`);
  return priceId;
}

export async function getOrCreateCheckoutAttempt(
  accountId: string,
  planKey: string,
  returnPath: string,
  attribution: Record<string, unknown>,
): Promise<CheckoutAttempt> {
  const result = await queryProductDatabase<{
    id: string;
    idempotency_key: string;
    plan_key: string;
    return_path: string;
    attribution: Record<string, unknown>;
  }>(
    `insert into billing_checkout_attempts (account_id, plan_key, return_path, attribution)
     values ($1, $2, $3, $4::jsonb)
     on conflict (account_id, plan_key) where status in ('pending', 'created')
     do update set updated_at = now()
     returning id, idempotency_key, plan_key, return_path, attribution`,
    [accountId, planKey, returnPath, JSON.stringify(attribution)],
  );
  const row = result.rows[0];
  if (!row?.idempotency_key?.trim()) throw new Error("Checkout attempt has no idempotency identity");
  return {
    id: row.id,
    idempotencyKey: row.idempotency_key,
    planKey: row.plan_key,
    returnPath: row.return_path,
    attribution: row.attribution,
  };
}

export async function recordCheckoutSession(attemptId: string, sessionId: string): Promise<void> {
  await queryProductDatabase(
    `update billing_checkout_attempts
        set status = 'created', provider_session_id = $2, updated_at = now()
      where id = $1`,
    [attemptId, sessionId],
  );
}

function eventObject(event: BillingEvent): Record<string, unknown> {
  return event.data?.object ?? {};
}

function nestedRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function providerId(value: unknown): string {
  if (typeof value === "string") return value.trim();
  return String(nestedRecord(value).id ?? "").trim();
}

function eventPriceId(object: Record<string, unknown>): string {
  const direct = providerId(object.price);
  if (direct) return direct;
  const items = nestedRecord(object.items);
  const rows = Array.isArray(items.data) ? items.data : [];
  const first = nestedRecord(rows[0]);
  return providerId(first.price);
}

async function resolveEventAccount(client: PoolClient, event: BillingEvent): Promise<string> {
  const object = eventObject(event);
  const direct = String(object.client_reference_id ?? "").trim();
  if (direct) return direct;
  const customer = providerId(object.customer);
  const subscription = providerId(object.subscription) || providerId(object.id);
  const result = await client.query<{ account_id: string }>(
    `select account_id from account_billing
      where ($1 <> '' and provider_customer_id = $1)
         or ($2 <> '' and provider_subscription_id = $2)
      limit 1`,
    [customer, subscription],
  );
  const accountId = result.rows[0]?.account_id;
  if (!accountId) throw new Error("Payment event is not bound to a product account");
  return accountId;
}

export async function readBillingStateForEvent(event: BillingEvent): Promise<BillingState> {
  const object = eventObject(event);
  const direct = String(object.client_reference_id ?? "").trim();
  if (direct) return readBillingState(direct);
  const customer = providerId(object.customer);
  const subscription = providerId(object.subscription) || providerId(object.id);
  const result = await queryProductDatabase<{ account_id: string }>(
    `select account_id from account_billing
      where ($1 <> '' and provider_customer_id = $1)
         or ($2 <> '' and provider_subscription_id = $2)
      limit 1`,
    [customer, subscription],
  );
  const accountId = result.rows[0]?.account_id;
  if (!accountId) throw new Error("Payment event is not bound to a product account");
  return readBillingState(accountId);
}

export async function applyLiveBillingEvent(
  event: BillingEvent,
  transition: BillingTransition,
): Promise<{ duplicate: boolean; stale: boolean; accountId?: string }> {
  const client = await productDatabase().connect();
  try {
    await client.query("begin");
    const inserted = await client.query(
      `insert into processed_payment_events (event_id, event_type, event_created)
       values ($1, $2, $3) on conflict do nothing returning event_id`,
      [event.id, event.type, event.created],
    );
    if (!inserted.rowCount) {
      await client.query("rollback");
      return { duplicate: true, stale: false };
    }
    const accountId = await resolveEventAccount(client, event);
    const object = eventObject(event);
    const metadata = nestedRecord(object.metadata);
    const customerId = providerId(object.customer) || null;
    const subscriptionId = providerId(object.subscription) || null;
    const priceId = eventPriceId(object) || null;
    const locked = await client.query<{ last_event_created: string | number }>(
      "select last_event_created from account_billing where account_id = $1 for update",
      [accountId],
    );
    const previousCreated = Number(locked.rows[0]?.last_event_created ?? 0);
    if (!shouldApplyPaymentEvent(previousCreated, event.created)) {
      await client.query(
        "update processed_payment_events set account_id = $2 where event_id = $1",
        [event.id, accountId],
      );
      await client.query("commit");
      return { duplicate: false, stale: true, accountId };
    }
    let boundPlanKey = "";
    if (priceId) {
      const binding = await client.query<{ plan_key: string }>(
        "select plan_key from billing_provider_bindings where provider_price_id = $1",
        [priceId],
      );
      boundPlanKey = binding.rows[0]?.plan_key ?? "";
    }
    const planKey = String(boundPlanKey || transition.plan_key || metadata.plan_key || "free");
    await client.query(
      `insert into account_billing (
         account_id, plan_key, subscription_status, provider_customer_id,
         provider_subscription_id, provider_price_id, current_period_end,
         cancel_at_period_end, last_event_id, last_event_created
       ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
       on conflict (account_id) do update set
         plan_key = excluded.plan_key,
         subscription_status = excluded.subscription_status,
         provider_customer_id = coalesce(excluded.provider_customer_id, account_billing.provider_customer_id),
         provider_subscription_id = coalesce(excluded.provider_subscription_id, account_billing.provider_subscription_id),
         provider_price_id = coalesce(excluded.provider_price_id, account_billing.provider_price_id),
         current_period_end = coalesce(excluded.current_period_end, account_billing.current_period_end),
         cancel_at_period_end = excluded.cancel_at_period_end,
         last_event_id = excluded.last_event_id,
         last_event_created = excluded.last_event_created,
         updated_at = now()`,
      [
        accountId,
        planKey,
        transition.subscription_status,
        transition.customer_id ?? customerId,
        transition.subscription_id ?? subscriptionId,
        transition.price_id ?? priceId,
        transition.current_period_end ?? null,
        transition.cancel_at_period_end ?? false,
        event.id,
        event.created,
      ],
    );
    if (transition.access === "grant") {
      await client.query(
        "update entitlement_grants set revoked_at = coalesce(revoked_at, now()) where account_id = $1 and source like 'subscription:%' and source <> $2",
        [accountId, `subscription:${planKey}`],
      );
      for (const capability of billingPlan(planKey).entitlements) {
        await client.query(
          `insert into entitlement_grants (account_id, capability, source, active_until)
           values ($1, $2, $3, $4)
           on conflict (account_id, capability, source) do update set
             active_until = excluded.active_until, revoked_at = null`,
          [accountId, capability, `subscription:${planKey}`, transition.current_period_end ?? null],
        );
      }
    } else if (transition.access === "revoke") {
      await client.query(
        "update entitlement_grants set revoked_at = coalesce(revoked_at, now()) where account_id = $1 and source like 'subscription:%'",
        [accountId],
      );
    }
    const checkoutAttemptId = String(metadata.checkout_attempt_id ?? "").trim();
    if (checkoutAttemptId) {
      await client.query(
        `update billing_checkout_attempts
            set status = 'completed', updated_at = now()
          where id = $1 and account_id = $2`,
        [checkoutAttemptId, accountId],
      );
    }
    await client.query(
      "update processed_payment_events set account_id = $2 where event_id = $1",
      [event.id, accountId],
    );
    await client.query("commit");
    return { duplicate: false, stale: false, accountId };
  } catch (error) {
    await client.query("rollback").catch(() => undefined);
    throw error;
  } finally {
    client.release();
  }
}

export async function hasEntitlement(accountId: string, capability: string): Promise<boolean> {
  const result = await queryProductDatabase(
    `select 1 from entitlement_grants
      where account_id = $1 and capability = $2 and revoked_at is null
        and active_from <= now()
        and (active_until is null or active_until > now())
      limit 1`,
    [accountId, capability],
  );
  if (result.rowCount) return true;
  const state = await readBillingState(accountId);
  return state.status === "free" && billingPlan("free").entitlements.includes(capability);
}
