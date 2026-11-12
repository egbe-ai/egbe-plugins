const STATUSES = new Set(["free", "trialing", "active", "past_due", "canceling", "paused", "canceled"]);

function unixDate(value) {
  const timestamp = Number(value || 0);
  return timestamp > 0 ? new Date(timestamp * 1000).toISOString() : null;
}

function subscriptionStatus(object, fallback) {
  const value = String(object.status || fallback || "free");
  if (value === "unpaid" || value === "incomplete" || value === "incomplete_expired") return "past_due";
  return STATUSES.has(value) ? value : "free";
}

export function reduceBillingEvent(current, event) {
  const object = event?.data?.object || {};
  const metadata = object.metadata || {};
  const base = {
    subscription_status: current?.subscription_status || current?.status || "free",
    access: "preserve",
    plan_key: metadata.plan_key || current?.plan_key || current?.planKey || null,
    customer_id: object.customer || current?.customer_id || current?.customerId || null,
    subscription_id: object.subscription || current?.subscription_id || current?.subscriptionId || null,
    price_id: object.price?.id || object.price || current?.price_id || current?.priceId || null,
    current_period_end:
      unixDate(object.current_period_end) || current?.current_period_end || current?.currentPeriodEnd || null,
    cancel_at_period_end: Object.hasOwn(object, "cancel_at_period_end")
      ? Boolean(object.cancel_at_period_end)
      : Boolean(current?.cancel_at_period_end ?? current?.cancelAtPeriodEnd),
  };
  switch (String(event?.type || "")) {
    case "checkout.session.completed":
      if (!new Set(["paid", "no_payment_required"]).has(String(object.payment_status || ""))) {
        return base;
      }
      return { ...base, subscription_status: "active", access: "grant" };
    case "checkout.session.async_payment_succeeded":
      return { ...base, subscription_status: "active", access: "grant" };
    case "customer.subscription.created":
    case "customer.subscription.updated": {
      const status = subscriptionStatus(object, base.subscription_status);
      return {
        ...base,
        subscription_status: object.cancel_at_period_end && status === "active" ? "canceling" : status,
        subscription_id: object.id || base.subscription_id,
        access: new Set(["active", "trialing", "canceling"]).has(status)
          ? "grant"
          : status === "canceled"
            ? "revoke"
            : "preserve",
      };
    }
    case "customer.subscription.paused":
      return { ...base, subscription_status: "paused", subscription_id: object.id || base.subscription_id };
    case "customer.subscription.resumed":
      return { ...base, subscription_status: "active", subscription_id: object.id || base.subscription_id, access: "grant" };
    case "customer.subscription.deleted":
      return { ...base, subscription_status: "canceled", subscription_id: object.id || base.subscription_id, access: "revoke" };
    case "invoice.paid":
      return { ...base, subscription_status: "active", access: "grant" };
    case "invoice.payment_failed":
      return { ...base, subscription_status: "past_due", access: "preserve" };
    case "charge.refunded":
      return base;
    default:
      return base;
  }
}

export function testLifecycleState(event, scenario) {
  const object = event?.data?.object || {};
  if (scenario === "checkout") return { subscription_status: "free", plan_key: object.metadata?.plan_key || "free" };
  return {
    subscription_status: "active",
    plan_key: object.metadata?.plan_key || "paid",
    customer_id: object.customer || "cus_test",
    subscription_id: object.subscription || "sub_test",
  };
}

export function shouldApplyPaymentEvent(previousCreated, nextCreated) {
  return Number(nextCreated) >= Number(previousCreated || 0);
}
