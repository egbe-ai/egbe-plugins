# Plan Catalog Contract

Define one server-owned catalog and import it wherever the product needs plan
information. Do not duplicate pricing arrays between landing, checkout, and the
account area.

Each plan needs:

- stable `plan_key` used in product routes and forms;
- display name and customer-facing feature summary;
- billing kind: `free`, `one_time`, or `subscription`;
- amount in cents, currency, and recurring interval when applicable;
- provider product and price ids for paid plans;
- the entitlements granted by the plan;
- whether the plan is selectable, current, or retired.

The browser may submit `plan_key`. The server resolves all provider ids and
amounts from the catalog. Reject unknown, retired, or mismatched plans. Never
accept an arbitrary Stripe price, customer, success URL, webhook path, or
entitlement list from the browser.

Create provider products and prices once with stable idempotency keys such as:

```text
catalog:<product-slug>:<plan-key>:product:v1
catalog:<product-slug>:<plan-key>:price:<amount>:<currency>:<interval>
```

Attach stable product routing metadata when creating provider products and
prices:

```json
{
  "plan_key": "pro",
  "payment_gateway_app_slug": "product-slug",
  "payment_gateway_webhook_path": "/api/payments/webhook"
}
```

This metadata is provider readback for lifecycle routing. Do not rely on a
browser checkout run or a previously created Checkout Session to rediscover the
webhook target.

If pricing changes, create a new Stripe price and update the catalog binding;
do not mutate historical price meaning. Confirm the resulting product and price
through `GET /payments/evidence`.
