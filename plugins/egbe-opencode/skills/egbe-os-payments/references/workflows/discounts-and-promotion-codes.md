# Discounts And Promotion Codes Workflow

Use this workflow to add or operate customer-entered promotion codes and
automatic Checkout discounts. It is complete for any product repository; a
materialized Billing foundation is optional.

## Product boundary

Continue the product's existing auth, account, billing configuration, database,
Checkout, and deployment conventions. Use only the server-side `OS_URL` and
`OS_API_KEY`. Never request Stripe credentials, call Stripe directly, or expose
provider ids to browser code.

A coupon defines the discount and must be restricted to one or more Stripe
Products already owned by this product. A promotion code is the text a customer
enters and always points to one owned coupon. Coupon records are historical
provider state: do not delete them. To stop customer use, deactivate the
promotion code.

### Production database access from a local agent

The managed `DATABASE_URL` is for the deployed runtime and may use a private
network address. Do not connect to it from a local machine and do not build a
temporary product endpoint for database maintenance. Fetch the existing
database access bundle through Egbe OS:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/deploy/<slug>/db" -fsS
```

The standard response envelope's `data` contains `apiUrl`, `schema`, `anonKey`,
and a temporary product-scoped `token`. Determine the real table, filter, and
column names from the product's migrations and data-access code. Read through
PostgREST with the returned schema:

```bash
curl -fsS \
  "$DB_API_URL/rest/v1/<table>?<filter-column>=eq.<encoded-value>&select=<columns>" \
  -H "apikey: $DB_ANON_KEY" \
  -H "Authorization: Bearer $DB_TOKEN" \
  -H "Accept-Profile: $DB_SCHEMA"
```

For writes, use `Content-Profile` and the same scoped credentials:

```bash
curl -fsS -X PATCH \
  "$DB_API_URL/rest/v1/<table>?<filter-column>=eq.<encoded-value>" \
  -H "apikey: $DB_ANON_KEY" \
  -H "Authorization: Bearer $DB_TOKEN" \
  -H "Content-Profile: $DB_SCHEMA" \
  -H "Accept-Profile: $DB_SCHEMA" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d '{"<column>":"<value>"}'
```

Keep these values in process memory only. Never commit them, place them in a
product `.env`, expose them to browser code, or reuse an expired token; fetch a
fresh bundle instead. If the scoped REST fields are unavailable, stop rather
than falling back to the private `DATABASE_URL`.

## Create and read back provider resources

Discover the current route contract first:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/payments/skill" -s
```

Create a percent coupon for an owned Stripe Product:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/payments/coupons" -s -X POST  \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: coupon:<stable-logical-name>" \
  -d '{
    "percent_off": 20,
    "duration": "once",
    "applies_to": {"products": ["prod_..."]},
    "name": "Launch offer"
  }'
```

For a fixed discount, use `amount_off` in the smallest currency unit together
with `currency`. Optional bounds are `max_redemptions`, `redeem_by`, and, for
`duration: "repeating"`, `duration_in_months`. Never omit
`applies_to.products`; product credentials cannot create an account-wide
coupon.

Read back only the current product's resources:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/payments/coupons" -s
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/payments/coupons/coupon_..." -s
```

Create a customer-facing code over the owned coupon, then read it back:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/payments/promotion-codes" -s -X POST  \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: promotion-code:<stable-logical-name>" \
  -d '{"coupon":"coupon_...","code":"WELCOME20"}'

OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/payments/promotion-codes?active=true" -s
```

An active code collision returns `409`. Choose the intended product-facing code
explicitly; do not retry with generated suffixes. To stop one code without
changing its coupon or sibling codes:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/payments/promotion-codes/promo_.../deactivate" -s -X POST
```

## Customer-specific codes

Customer eligibility begins in the product database, not in Stripe. Before any
provider request, load every requested email from the product's authoritative
account table. Reject the whole operation when an email has no account or maps
to more than one account. An explicit founder-provided email list is input to
that lookup; it is not proof that the accounts exist.

Each eligible account must have exactly one server-only Stripe Customer binding
persisted on its account or billing record. When a real account has no binding,
create the Customer explicitly and idempotently, then persist the returned id
before creating any Promotion Code:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/payments/customers" -s -X POST  \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: customer:<stable-product-account-id>" \
  -d '{"email":"verified-account@example.com"}'
```

Do not create another Customer when the account already has a binding or when
a prior trusted OS operation returned the exact owned Customer for that
account; validate and persist the existing id instead. If the correct existing
Customer cannot be identified unambiguously, stop and reconcile the binding.
Never guess from matching email alone inside product code.

After the binding transaction commits, create the restricted Promotion Code
with the exact Customer id:

```json
{
  "coupon": "coupon_...",
  "code": "PRIVATE20",
  "customer": "cus_..."
}
```

The gateway retrieves that Customer and returns `404` unless it belongs to the
current product. Stripe enforces the resulting code against that exact Customer,
not against an email string. Both Checkout validation and real Checkout must
therefore send the same server-loaded `customer`; `customer_email` is not an
equivalent binding.

For a founder-selected list of existing product-account emails, use the bounded
batch operation with one stable operation id:

```bash
OS_AGENT_NAME="<your agent name>" python3 "<skills-directory>/egbe-os-quickstart/scripts/egbe-curl.py" --egbe-request "/payments/promotion-codes/batch" -s -X POST  \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: promotion-code:<stable-recipient-list-operation>" \
  -d '{
    "coupon":"coupon_...",
    "code":"FOUNDERS20",
    "customer_emails":["first@example.com","second@example.com"]
  }'
```

Use the batch only after every email passed the account lookup and every account
already stores its Stripe Customer binding. The gateway resolves existing owned
Customers but never creates them in this operation. A missing binding returns
`409 customer_binding_required`; multiple owned Customers with the same email
return `409 ambiguous_customer_email`. Either error occurs during full-list
preflight, before any Promotion Code is created. Fix the account bindings, then
retry the same logical request and `Idempotency-Key`.

The same visible code may be used for different restricted Customers. Confirm
that every returned `email` → `customer` mapping exactly matches the binding
already stored on the corresponding account. A mismatch is a failed operation;
do not offer Checkout until it is reconciled.

Store the selected coupon or promotion-code provider reference in the
product's existing server-only billing configuration or database. Keep the
customer-visible code and commercial meaning in the product-owned catalog.
Never put provider ids in `NEXT_PUBLIC_*`, page markup, browser storage, or a
client-supplied Checkout payload.

## Customer-entered codes

New Checkout implementations enable the hosted Checkout entry field by
default. Build this value on the server:

```json
{
  "allow_promotion_codes": true
}
```

Pass it in both `POST /payments/checkout-sessions/validate` and
`POST /payments/checkout-sessions`, preserving every other field and the same
logical-attempt identity from the product checkout workflow. Existing Checkout
calls that intentionally omit the field keep their existing behavior.

Payment Links support the same `allow_promotion_codes` boolean. They do not
accept automatic `discounts`.

When the product issues customer-restricted codes, load the persisted Customer
id with the authenticated account and include `customer: "cus_..."` in both
Checkout validation and creation. Sending only `customer_email` makes the
restricted code invalid on Stripe-hosted Checkout even when the typed email is
identical.

## Automatic Checkout discount

Choose exactly one server-owned reference; sending `discounts` by itself
already disables customer code entry:

```json
{
  "discounts": [{"coupon": "coupon_..."}]
}
```

or:

```json
{
  "discounts": [{"promotion_code": "promo_..."}]
}
```

Do not combine `allow_promotion_codes` with `discounts`. Stripe rejects the
pair even when the value is `false`; the gateway accepts an explicit
`allow_promotion_codes: false` alongside `discounts` and strips it before
calling Stripe, while `allow_promotion_codes: true` with `discounts` is
rejected as ambiguous.

The browser may choose a product-owned offer key, but it must never supply the
provider reference. Resolve that key to the stored server-side reference after
authentication and plan validation. The gateway rejects multiple discounts,
foreign resources, discounts that do not apply to the purchased Stripe
Product, a customer-restricted code without its exact owned Checkout Customer,
and a payload that combines automatic discounting with customer code entry.

## Verification

1. Read back the coupon and promotion code through the scoped list and detail
   routes.
2. Run the normal Checkout `validate-only` path with the final discount mode.
   Confirm `data.discount_mode`, `data.discount_reference`, and
   `data.allow_promotion_codes`; no Checkout Session may be created.
3. Create a real Checkout Session only from an explicit user mutation and
   verify the hosted page exposes the intended customer-code field or applied
   automatic discount.
4. Exercise the signed lifecycle workflow. Discounted completion must update
   the same subscription and entitlement state as a full-price purchase; it
   must not enter wallet top-up finalization.
5. On product archive or disable-sales, confirm every owned active promotion
   code becomes inactive while coupons remain available as historical
   readback.
