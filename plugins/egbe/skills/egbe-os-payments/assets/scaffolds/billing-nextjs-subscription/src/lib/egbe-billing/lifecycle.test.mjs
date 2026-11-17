import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";

import { reduceBillingEvent, shouldApplyPaymentEvent } from "./lifecycle.mjs";
import { verifyPaymentSignature } from "./signature.mjs";

test("checkout grants the selected plan", () => {
  const transition = reduceBillingEvent(
    { subscription_status: "free", plan_key: "free" },
    {
      type: "checkout.session.completed",
      data: {
        object: {
          payment_status: "paid",
          customer: "cus_1",
          subscription: "sub_1",
          metadata: { plan_key: "pro" },
        },
      },
    },
  );
  assert.equal(transition.subscription_status, "active");
  assert.equal(transition.plan_key, "pro");
  assert.equal(transition.access, "grant");
});

test("an unpaid checkout return never grants subscription access", () => {
  const transition = reduceBillingEvent(
    { subscription_status: "free", plan_key: "free" },
    {
      type: "checkout.session.completed",
      data: { object: { payment_status: "unpaid", metadata: { plan_key: "pro" } } },
    },
  );
  assert.equal(transition.subscription_status, "free");
  assert.equal(transition.access, "preserve");
});

test("failure and refund preserve access while effective cancellation revokes", () => {
  const current = { subscription_status: "active", plan_key: "pro" };
  assert.equal(reduceBillingEvent(current, { type: "invoice.payment_failed", data: { object: {} } }).access, "preserve");
  assert.equal(reduceBillingEvent(current, { type: "customer.subscription.deleted", data: { object: {} } }).access, "revoke");
  assert.equal(reduceBillingEvent(current, { type: "charge.refunded", data: { object: {} } }).access, "preserve");
});

test("camel-case repository state remains authoritative when an event omits fields", () => {
  const transition = reduceBillingEvent(
    {
      status: "active",
      planKey: "pro",
      customerId: "cus_1",
      subscriptionId: "sub_1",
      cancelAtPeriodEnd: true,
    },
    { type: "invoice.payment_failed", data: { object: {} } },
  );
  assert.equal(transition.plan_key, "pro");
  assert.equal(transition.customer_id, "cus_1");
  assert.equal(transition.subscription_id, "sub_1");
  assert.equal(transition.cancel_at_period_end, true);
});

test("out-of-order events cannot replace newer authoritative state", () => {
  assert.equal(shouldApplyPaymentEvent(1_900_000_010, 1_900_000_009), false);
  assert.equal(shouldApplyPaymentEvent(1_900_000_010, 1_900_000_010), true);
  assert.equal(shouldApplyPaymentEvent(1_900_000_010, 1_900_000_011), true);
});

test("signature verification rejects stale and invalid input", () => {
  const now = 1_900_000_000;
  const body = '{"id":"evt_1"}';
  const digest = createHmac("sha256", "secret").update(`${now}.${body}`).digest("hex");
  assert.equal(verifyPaymentSignature(body, `t=${now},v1=${digest}`, "secret", now), now);
  assert.throws(() => verifyPaymentSignature(body, `t=${now - 301},v1=${digest}`, "secret", now), /Stale/);
  assert.throws(() => verifyPaymentSignature(body, `t=${now},v1=${"0".repeat(64)}`, "secret", now), /Invalid/);
});

test("signature verification allows 60 seconds of clock skew and five minutes of age", () => {
  const now = 1_900_000_000;
  const body = '{"id":"evt_clock_boundary"}';
  const header = (offset, secret = "secret") => {
    const timestamp = now + offset;
    const digest = createHmac("sha256", secret).update(`${timestamp}.${body}`).digest("hex");
    return `t=${timestamp},v1=${digest}`;
  };
  for (const offset of [-300, 0, 1, 60]) {
    assert.equal(verifyPaymentSignature(body, header(offset), "secret", now), now + offset);
    assert.throws(() => verifyPaymentSignature(body, header(offset, "other"), "secret", now), /Invalid/);
  }
  for (const offset of [-301, 61]) {
    assert.throws(() => verifyPaymentSignature(body, header(offset), "secret", now), /Stale/);
  }
});
