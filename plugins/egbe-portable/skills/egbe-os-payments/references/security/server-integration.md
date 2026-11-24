# Server Integration And Credentials

## Signed webhook credentials

For app-bound keys and direct status reads, see
[Checkout and status through OS](#checkout-and-status-through-os).

The deployed product backend uses the same canonical OS contract as every other
product capability: server-only `OS_URL` and `OS_API_KEY`. Site Gateway injects
the product-purpose identity authoritatively; the agent must not receive, mint,
copy, rename, or deploy it.

The product webhook secret proves webhook authenticity and is not an OS access
credential. Obtain the current product secret from
`GET /payments/webhook-secret` with the current workload credential and pass
only `EGBE_PAYMENT_WEBHOOK_SECRET` as a server-only runtime environment value
through the active Egbe OS deployment mechanism. Capture the response without
printing it. Never write the secret to source, a repository env file, or a
durable workflow artifact.

The deployment mechanism may authoritatively set or refresh the same value with
the current product secret. This is intentional and does not change the agent
workflow.

Never place these values in source, browser bundles, logs, analytics payloads,
or `NEXT_PUBLIC_*` variables. Product routes must call OS from the server.

The deploy mechanism preserves the secret during code-only redeploys. A later
full env update must keep the current product webhook secret. Product OS
credential rotation is owned by the platform and takes effect on the next
deployment.

## Checkout and status through OS

The product backend creates Checkout and reads current Stripe status through OS.
Keep local account, order, and entitlement records in the product database.
Payment Gateway reads Stripe on demand. This integration uses a server OS key
and outgoing HTTPS requests.

### Connect the app

1. Create the catalogue with the founder's existing Payments capability. Set
   `app_slug` on the product and price metadata to match this application.
   Keep the existing Stripe price IDs that already belong to this app.
2. On Egbe, deploy with `payment_status: true` in `POST /deploy` or
   `POST /deploy/{slug}/convex/deploy`. Site Gateway injects an app-bound
   `OS_API_KEY` into the backend. Later deploys can omit the field.
3. On external hosting, the owner uses the project primary key to send
   `PUT /payments/apps/{slug}/domain` with `{"origin":"https://app.example.com"}`.
   Publish the returned `challenge` as the content of `verification_url`.
   Call `POST /payments/apps/{slug}/domain/verify` within 30 minutes. The file
   must be served over HTTPS at that exact address without redirects. Remove the
   file after verification and repeat the process when the domain changes.
4. The external app owner calls `POST /payments/apps/{slug}/key` and copies
   `data.OS_API_KEY` from the response to the app's private server environment
   as `OS_API_KEY`, alongside the Egbe `OS_URL`. Issuing another key replaces
   the previous key. Use `DELETE /payments/apps/{slug}/key` to revoke access.
   Keep all credentials out of browser code, logs, and source.

### Handle checkout and refresh

- After the server authenticates the product account, call
  `POST /payments/app/checkout-sessions` with `price`, `mode` (`payment` or
  `subscription`), an opaque local `client_reference_id`, `success_path`, and
  `cancel_path`. Checkout enables promotion codes by default. Send an
  `Idempotency-Key` stable for this checkout attempt. Save
  `data.id` against the local order or account before redirecting to `data.url`.
- When the user returns, load the saved ID for that signed-in account and call
  `GET /payments/app/checkout-sessions/{id}`. Check `livemode`,
  `client_reference_id`, `payment_status`, and applicable refund information.
  Checkout can be complete while payment is still pending. A free trial or
  zero-amount Checkout can report `no_payment_required`; apply the product's
  trial or free-order policy. Record fulfillment idempotently in the product.
- Save any returned `subscription_id` to the local account. Read
  `GET /payments/app/subscriptions/{id}` for current status, period, scheduled
  cancellation, pause state, prices, and the latest invoice and its refund
  details when Stripe returns a charge. Refund information is scoped to the
  checkout charge or the latest subscription invoice. Amounts use the
  currency's minor unit. Use the confirmed
  provider facts to update local access.
- Periodically refresh pending orders and active subscriptions by their stored
  IDs, including when the buyer has left the site. A transient error or rate
  limit means the current state is unknown. Keep the last confirmed state
  separate and retry with backoff. Apply a newly confirmed order once.
- To open Customer Portal for a subscription created by this contract, call
  `POST /payments/app/portal-sessions` with the subscription ID saved for the
  signed-in account and a relative `return_path`. Redirect to the returned URL.

### Verify and migrate

Use test-mode fixtures to prove checkout, return, confirmed status and the
product's access or fulfillment behavior. Test pending payments, renewal,
cancellation and refund. Verify test sessions cannot grant live access.
Reload the product's server-side billing state to prove the update persisted.

If migrating, first verify ownership and readback of existing checkout and
subscription IDs. Preserve current paid access and the signed receiver for
existing checkouts until the owner has confirmed the switchover. Keep apps
that still require the legacy Customer Portal on their existing runtime
contract. The app-bound Portal supports subscriptions created by this API.
Egbe-hosted apps can deploy with `payment_status: false` to restore their
previous runtime credential.
