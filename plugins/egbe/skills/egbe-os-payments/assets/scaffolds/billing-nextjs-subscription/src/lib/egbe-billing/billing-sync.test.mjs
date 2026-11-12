import assert from "node:assert/strict";
import test from "node:test";

import { metadataFor, validateCatalog } from "../../../scripts/billing-sync.mjs";

const validCatalog = () => ({
  catalog_version: 1,
  app_slug: "example-product",
  plans: [
    {
      plan_key: "free",
      display_name: "Free",
      summary: "Free access",
      kind: "free",
      amount_cents: 0,
      currency: "usd",
      interval: null,
      entitlements: [],
      selectable: true,
    },
    {
      plan_key: "pro",
      display_name: "Pro",
      summary: "Paid access",
      kind: "subscription",
      amount_cents: 1900,
      currency: "usd",
      interval: "month",
      entitlements: ["book.create"],
      selectable: true,
    },
  ],
});

test("catalog validation requires one provider-free subscription contract", () => {
  const result = validateCatalog(validCatalog());
  assert.equal(result.appSlug, "example-product");
  assert.deepEqual(result.paid.map((plan) => plan.plan_key), ["pro"]);
  assert.equal("provider_price_id" in result.paid[0], false);
});

test("catalog validation rejects duplicate identities and incomplete pricing", () => {
  const duplicate = validCatalog();
  duplicate.plans[1].plan_key = "free";
  assert.throws(() => validateCatalog(duplicate), /duplicate/);

  const incomplete = validCatalog();
  incomplete.plans[1].amount_cents = 0;
  assert.throws(() => validateCatalog(incomplete), /amount_cents/);
});

test("provider metadata binds one plan to the deployed product webhook", () => {
  assert.deepEqual(metadataFor("example-product", "pro"), {
    plan_key: "pro",
    payment_gateway_app_slug: "example-product",
    payment_gateway_webhook_path: "/api/payments/webhook",
  });
});
