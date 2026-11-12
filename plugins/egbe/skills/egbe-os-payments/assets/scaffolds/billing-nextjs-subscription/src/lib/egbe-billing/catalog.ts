import "server-only";

import rawCatalog from "./plans.json";

export type BillingPlan = {
  planKey: string;
  displayName: string;
  summary: string;
  kind: "free" | "subscription";
  amountCents: number;
  currency: string;
  interval: "month" | "year" | null;
  entitlements: readonly string[];
  selectable: boolean;
};

export type BillingCatalog = {
  version: number;
  appSlug: string;
  plans: readonly BillingPlan[];
};

function readCatalog(): BillingCatalog {
  if (rawCatalog.catalog_version !== 1) {
    throw new Error("Unsupported billing catalog version");
  }
  const appSlug = rawCatalog.app_slug.trim();
  if (appSlug && !/^[a-z0-9][a-z0-9-]{0,62}$/.test(appSlug)) {
    throw new Error("Billing catalog app_slug is invalid");
  }
  const plans = rawCatalog.plans.map((plan) => ({
    planKey: plan.plan_key,
    displayName: plan.display_name,
    summary: plan.summary,
    kind: plan.kind,
    amountCents: plan.amount_cents,
    currency: plan.currency.toLowerCase(),
    interval: plan.interval,
    entitlements: plan.entitlements,
    selectable: plan.selectable,
  })) as BillingPlan[];
  const keys = new Set<string>();
  for (const plan of plans) {
    if (!/^[a-z][a-z0-9_-]{1,63}$/.test(plan.planKey) || keys.has(plan.planKey)) {
      throw new Error(`Invalid or duplicate billing plan key: ${plan.planKey}`);
    }
    keys.add(plan.planKey);
    if (!plan.displayName.trim() || !plan.summary.trim()) {
      throw new Error(`Billing plan ${plan.planKey} requires display content`);
    }
    if (!/^[a-z]{3}$/.test(plan.currency) || typeof plan.selectable !== "boolean") {
      throw new Error(`Billing plan ${plan.planKey} has an invalid commercial contract`);
    }
    if (new Set(plan.entitlements).size !== plan.entitlements.length) {
      throw new Error(`Billing plan ${plan.planKey} has duplicate entitlements`);
    }
    if (plan.kind === "subscription" && (!plan.interval || plan.amountCents < 1)) {
      throw new Error(`Subscription plan ${plan.planKey} has incomplete pricing`);
    }
  }
  if (!keys.has("free")) throw new Error("Billing catalog must define the free plan");
  return {
    version: rawCatalog.catalog_version,
    appSlug,
    plans,
  };
}

export const billingCatalog = readCatalog();

export function billingPlan(planKey: string): BillingPlan {
  const plan = billingCatalog.plans.find((candidate) => candidate.planKey === planKey);
  if (!plan) throw new Error("Unknown billing plan");
  return plan;
}

export function formatPlanAmount(plan: BillingPlan): string {
  return new Intl.NumberFormat("en", {
    style: "currency",
    currency: plan.currency,
  }).format(plan.amountCents / 100);
}
