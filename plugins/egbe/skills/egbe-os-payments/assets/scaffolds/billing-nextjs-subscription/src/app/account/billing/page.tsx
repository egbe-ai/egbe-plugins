import Link from "next/link";

import { ProductAuthenticationRequired, requireProductAccount } from "@/lib/egbe-product";
import {
  billingCatalog,
  billingPlan,
  formatPlanAmount,
  type BillingPlan,
} from "@/lib/egbe-billing/catalog";
import { readBillingState, type BillingState } from "@/lib/egbe-billing/repository";

const WARNING_STATES = new Set(["past_due", "canceling", "paused"]);

type BillingPageModel =
  | { kind: "signed-out" }
  | { kind: "unavailable" }
  | {
      kind: "ready";
      state: BillingState;
      current: BillingPlan;
      upgrade?: BillingPlan;
    };

async function loadBillingPage(): Promise<BillingPageModel> {
  try {
    const account = await requireProductAccount();
    const state = await readBillingState(account.id);
    const current =
      billingCatalog.plans.find((plan) => plan.planKey === state.planKey) ??
      billingPlan("free");
    const upgrade = billingCatalog.plans.find(
      (plan) => plan.kind === "subscription" && plan.selectable,
    );
    return { kind: "ready", state, current, upgrade };
  } catch (error) {
    if (error instanceof ProductAuthenticationRequired) return { kind: "signed-out" };
    console.error("billing page failed", error);
    return { kind: "unavailable" };
  }
}

export default async function AccountBillingPage() {
  const model = await loadBillingPage();
  if (model.kind === "signed-out") {
    return (
      <main data-billing-page>
        <h1>Billing</h1>
        <p>Sign in through the product account journey to view billing.</p>
        <Link href="/login?next=/account/billing">Sign in</Link>
      </main>
    );
  }
  if (model.kind === "unavailable") {
    return (
      <main data-billing-page>
        <h1>Billing</h1>
        <p data-billing-error>Billing information is temporarily unavailable. Please try again.</p>
        <Link href="/account/billing">Retry</Link>
      </main>
    );
  }

  const { current, state, upgrade } = model;
  const paid = current.kind === "subscription";
  const warning = WARNING_STATES.has(state.status);
  return (
    <main data-billing-page aria-labelledby="billing-title">
      <header>
        <p>Account</p>
        <h1 id="billing-title">Billing</h1>
        <p>Understand your current plan and manage it safely.</p>
      </header>
      <section aria-label="Current billing state">
        <div data-billing-plan={current.planKey}>
          <span>Current plan</span>
          <strong>{current.displayName}</strong>
        </div>
        <div data-billing-status={state.status}>
          <span>Status</span>
          <strong>{state.status.replace("_", " ")}</strong>
        </div>
        <div>
          <span>Price</span>
          <strong>
            {current.kind === "free"
              ? "Free"
              : `${formatPlanAmount(current)} / ${current.interval}`}
          </strong>
        </div>
        {state.currentPeriodEnd ? (
          <div>
            <span>{state.cancelAtPeriodEnd ? "Access until" : "Renews"}</span>
            <strong>{state.currentPeriodEnd.toLocaleDateString()}</strong>
          </div>
        ) : null}
      </section>
      {warning ? (
        <p role="status">
          Your subscription needs attention. Your current state remains authoritative until a signed payment update arrives.
        </p>
      ) : null}
      {paid && state.customerId ? (
        <form action="/api/billing/portal" method="post">
          <button type="submit" data-billing-action={state.status === "canceled" ? "reactivate" : "manage"}>
            Manage subscription
          </button>
        </form>
      ) : upgrade ? (
        <form action="/api/billing/checkout" method="post">
          <input type="hidden" name="plan_key" value={upgrade.planKey} />
          <button type="submit" data-billing-action="upgrade">
            Upgrade to {upgrade.displayName}
          </button>
        </form>
      ) : (
        <p>No paid plan has been configured yet.</p>
      )}
      <Link href="/">Return to the product</Link>
    </main>
  );
}
