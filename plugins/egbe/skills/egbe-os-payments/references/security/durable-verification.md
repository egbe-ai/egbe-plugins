# Verify durable payment effects without a charge

Use this for the product's actual paid promise, whether a one-time purchase or
subscription. Do not add subscription periods or quota machinery to a product
that does not promise them. Reuse its existing authentication, persistence and
payment implementation; this is verification, not a parallel billing system.

## Keep three proofs distinct

- Checkout validation and signed receipts prove configuration and binding.
- Signed gateway simulations prove signature handling and reducer behavior;
  their test-event branch must remain side-effect free in production.
- Durable integration tests prove the event transaction, stored entitlement
  and actual protected Product consumer. Neither of the first two proves this.

## Exercise the implementation against isolated durable state

Use a disposable test database or equivalent isolated persistence boundary, with
the normal migrations, transaction implementation, account/session resolver and
Product enforcement code. Establish isolation before sending any event. Keep
provider calls, real customer data, production credentials and production
storage outside this test. An unavailable isolated test mechanism is a concrete
verification gap, not permission to mutate production or invent success.

1. Record the code revision and configuration differences from the deployed
   product. Reuse its private validation identity pattern. Create only the
   minimum synthetic accounts, checkout binding and data in this isolated store.
   Keep access material private and identify all activity as testing.
2. Confirm the real protected action denies the unpaid account. Exercise the
   normal signed-event entry and durable transaction path using locally signed
   fixtures and a test-only secret in the isolated application. A production-like
   event fixture may reach that path only here; never strip test markers from a
   gateway event, change production test behavior or send a forged live event
   to the deployed receiver. Block external provider/analytics delivery.
3. Read back the committed event, correct account/offer mapping and entitlement
   through the actual persistence adapter. Reopen the connection or restart the
   test application, then verify the promised Product action, delivery and return
   access through its normal authorization path. Do not replace writes or access
   checks with mocks, a boolean preview flag or a test-only grant shortcut.
4. Verify a different account and signed-out access remain denied. Replay the
   same event and check that no extra entitlement, order or delivered unit is
   created. Exercise the product's actual refund/revocation policy and applicable
   ordering, concurrency and period/usage boundaries.
5. Force a persistence failure at the transaction boundary. Verify rollback and
   a retryable error, then retry and observe one committed result. A successful
   response before the durable commit is a failure even when the reducer passes.

Delete only the disposable test resources through the test environment's normal
cleanup. Retain bounded assertions, revision, isolation and cleanup evidence;
never raw credentials or invented customer/revenue totals.

## Verify the deployed boundary separately

On the deployed revision, retain the normal account-entry, unpaid access-denial,
checkout validate-only binding and signed no-side-effect simulation checks.
Confirm that the deployed consumer uses the implementation exercised above;
document configuration differences and any unverified live dependencies. An
owner-only preview can separately prove the proposed output is usable, but
cannot prove paid entitlement persistence or payment-driven fulfillment.

Report exactly which environment each observation covers. Isolated integration
success is not a live payment, a production transaction observation or revenue.
Missing deployed configuration, real delivery dependencies or independent
handoff evidence remain open; a local test does not close them by assertion.
